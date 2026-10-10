"""Một lượt của agent: dựng deps + agent, chạy, đổi kết quả thành `answer | proposal | clarification` + history.

Agent KHÔNG ghi dữ liệu: thứ duy nhất đi ra là `deps.outcome` (đề xuất, đã qua validator hợp đồng) hoặc
`deps.clarifications` (câu hỏi do tool viết). Lời dẫn cho đề xuất/câu hỏi do CODE dựng, không phải model viết.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any, Final, Literal

import httpx
from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import ContentFilterError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_ai_harness import CodeMode

from family_agent.contract import validate_operations
from family_agent.harness.code_guard import CodeGuard
from family_agent.harness.deps import AppDeps, ToolError, UserInfo, build_http_client
from family_agent.harness.end_when_settled import EndWhenSettled, is_settled
from family_agent.harness.prompts import build_instructions
from family_agent.harness.tools.ask import ask_toolset
from family_agent.harness.tools.plans import plan_toolset
from family_agent.harness.tools.read import load_members, read_toolset
from family_agent.harness.tools.shopping import shopping_toolset
from family_agent.harness.tools.tasks import task_toolset
from family_agent.harness.vocab import fold

log = logging.getLogger("family_agent.run")

Kind = Literal["answer", "proposal", "clarification"]

MSG_TOO_COMPLEX: Final = (
    "Câu hỏi hơi phức tạp nên mình chưa xử lý xong. Bạn thử hỏi gọn hơn hoặc chia nhỏ giúp mình nhé."
)
MSG_GAVE_UP: Final = "Mình chưa xử lý được yêu cầu này. Bạn thử diễn đạt lại hoặc hỏi ngắn gọn hơn giúp mình nhé."
MSG_BAD_PROPOSAL: Final = "Mình chưa lập được đề xuất hợp lệ. Bạn thử diễn đạt lại yêu cầu giúp mình nhé."
MSG_NO_ANSWER: Final = "Mình chưa có câu trả lời cho việc này. Bạn thử hỏi lại theo cách khác giúp mình nhé."

# Chỉ bắt khẳng định ngôi thứ nhất / đứng trần gửi người dùng; KHÔNG bắt câu đọc ngôi thứ ba
# ("Mẹ đã ghi 3 khoản chi", "Lan đã tạo việc này"). Hai mẫu vì "mình" (đại từ) khác "Minh" (tên) —
# chỉ phân biệt được khi còn dấu.
_FIRST_PERSON_RE: Final = re.compile(
    r"\b(?:mình|tôi|em)\s+(?:đã|vừa)\s+(?:thêm|xoá|xóa|tạo|cập nhật|ghi|đề xuất|đánh dấu|mua|sửa|giao)\b"
)
# Trên chuỗi đã bỏ dấu: đầu câu/đầu dòng, hoặc sau "ok/vâng/rồi/được/xong" — "đã thêm/xoá/xóa/tạo/cập nhật/ghi".
_BARE_RE: Final = re.compile(
    r"(?:^|[.!?\n:;]\s*|\b(?:ok|vang|roi|duoc|xong)[\s,.!:]+)(?:[-*]\s*)?da\s+(?:them|xoa|tao|cap nhat|ghi)\b"
)
_UNSTAGED_RETRY: Final = (
    "Bạn nói đã thay đổi dữ liệu nhưng chưa gọi tool propose_* nào, nên CHƯA có gì thay đổi. "
    "Hãy gọi đúng tool propose_* (người dùng sẽ bấm Duyệt) hoặc trả lời rằng bạn chưa thực hiện thay đổi."
)


@dataclass(frozen=True)
class TurnLimits:
    max_tool_calls: int = 40
    code_max_duration_s: float = 15.0  # Monty tính DỒN cho mọi run_code của lượt; chạy đồng bộ trên event loop
    code_max_memory: int = 128 * 1024 * 1024
    request_limit: int = 6
    http_timeout_s: float = 10.0
    max_history_turns: int = 20
    max_history_bytes: int = 1_000_000  # sau khi cắt 20 lượt, còn quá lớn thì bỏ nguyên lượt cũ nhất cho tới khi vừa


@dataclass
class TurnInput:
    message: str
    history: list[dict[str, Any]]
    user: UserInfo
    agent_token: str = field(repr=False)  # không để lọt vào repr/log
    today: str
    weekday: str


@dataclass
class TurnResult:
    kind: Kind
    reply: str
    history: list[Any]
    usage: dict[str, int]
    operations: list[dict[str, Any]] | None = None
    question: str | None = None
    options: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


async def _refuse_unstaged_change(ctx: RunContext[AppDeps], output: str) -> str:
    """Câu trả lời khẳng định đã thay đổi dữ liệu mà không có đề xuất nào → gửi lại cho model."""
    if is_settled(ctx.deps):
        return output
    # NFC trước: model/bàn phím có thể trả dấu rời (NFD) làm mẫu có dấu không khớp.
    if _FIRST_PERSON_RE.search(unicodedata.normalize("NFC", output).casefold()) or _BARE_RE.search(fold(output)):
        raise ModelRetry(_UNSTAGED_RETRY)
    return output


def _is_retry_exhaustion(e: UnexpectedModelBehavior) -> bool:
    """Chỉ "hết retry" (output validator / run_code) mới là lỗi của model đáng trả lời thân thiện."""
    return not isinstance(e, ContentFilterError) and re.search(r"max(?:imum)?\b.*\bretries", str(e), re.I) is not None


def build_agent(model: Model, limits: TurnLimits) -> Agent[AppDeps, str]:
    agent: Agent[AppDeps, str] = Agent(
        model,
        deps_type=AppDeps,
        instructions=lambda ctx: build_instructions(ctx.deps),
        toolsets=[read_toolset, shopping_toolset, task_toolset, plan_toolset, ask_toolset],
        capabilities=[
            CodeMode(
                max_tool_calls=limits.max_tool_calls,
                resource_limits={"max_duration_secs": limits.code_max_duration_s, "max_memory": limits.code_max_memory},
            ),
            CodeGuard(),
            EndWhenSettled(),
        ],
        retries={"tools": 1, "output": 2},
    )
    agent.output_validator(_refuse_unstaged_change)
    return agent


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def load_history(raw: list[dict[str, Any]]) -> list[ModelMessage]:
    """History không parse được (vd. sau nâng cấp thư viện) → bỏ, không làm hỏng lượt."""
    if not raw:
        return []
    try:
        parsed = list(ModelMessagesTypeAdapter.validate_python(raw))
    except ValidationError:
        log.warning(json.dumps({"event": "history_dropped", "messages": len(raw)}))
        return []
    # System prompt lưu trong history cũ không được tin/dùng lại — instructions luôn dựng mới mỗi lượt.
    cleaned: list[ModelMessage] = []
    for m in parsed:
        if isinstance(m, ModelRequest):
            parts = [p for p in m.parts if not isinstance(p, SystemPromptPart)]
            if not parts:
                continue
            m = replace(m, parts=parts)
        cleaned.append(m)
    return cleaned


def _starts_user_turn(m: ModelMessage) -> bool:
    return isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts)


def trim_history(messages: list[ModelMessage], max_turns: int) -> list[ModelMessage]:
    """Giữ `max_turns` lượt gần nhất, chỉ cắt ở tin nhắn người dùng (không để tool call/return mồ côi → 400)."""
    starts = [i for i, m in enumerate(messages) if _starts_user_turn(m)]
    if len(starts) <= max_turns:
        return messages
    return messages[starts[-max_turns]:]


def _dump_history(messages: list[ModelMessage], limits: TurnLimits) -> list[Any]:
    for m in messages:
        if isinstance(m, ModelRequest):
            m.instructions = None  # dựng lại mỗi lượt; lưu lại chỉ làm history phình
    kept = trim_history(messages, limits.max_history_turns)
    while True:
        out: list[Any] = ModelMessagesTypeAdapter.dump_python(kept, mode="json")
        turns = sum(1 for m in kept if _starts_user_turn(m))
        if turns <= 1 or len(json.dumps(out, ensure_ascii=False).encode()) <= limits.max_history_bytes:
            return out  # lượt cuối luôn giữ (kể cả khi một mình nó đã lớn)
        kept = trim_history(kept, turns - 1)


# ---------------------------------------------------------------------------
# Kết quả
# ---------------------------------------------------------------------------


def settle(
    deps: AppDeps, output: str | None
) -> tuple[Kind, str, list[dict[str, Any]] | None, str | None, list[str]]:
    """(kind, reply, operations, question, options) — câu hỏi thắng đề xuất; đề xuất phải hợp lệ theo hợp đồng."""
    asked = deps.clarifications.first()
    if asked is not None:
        return "clarification", asked.question, None, asked.question, list(asked.options)
    if not deps.outcome.is_empty():
        checked = validate_operations(deps.outcome.operations)
        if not checked.ok:  # không bao giờ trả đề xuất sai hợp đồng
            log.warning(json.dumps({"event": "proposal_invalid", "errors": len(checked.errors)}))
            return "answer", MSG_BAD_PROPOSAL, None, None, []
        n = len(checked.operations)
        return "proposal", f"Mình đề xuất {n} thay đổi — bạn xem và bấm Duyệt nhé.", checked.operations, None, []
    text = (output or "").strip()
    return "answer", text or MSG_NO_ANSWER, None, None, []


def _usage_dict(u: RunUsage) -> dict[str, int]:
    return {
        "requests": u.requests, "toolCalls": u.tool_calls,
        "inputTokens": u.input_tokens, "outputTokens": u.output_tokens,
    }


def _synthetic(user_text: str, reply: str) -> list[ModelMessage]:
    return [ModelRequest(parts=[UserPromptPart(user_text)]), ModelResponse(parts=[TextPart(reply)])]


async def run_turn(
    model: Model,
    inp: TurnInput,
    *,
    app_base_url: str,
    limits: TurnLimits | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TurnResult:
    limits = limits or TurnLimits()
    http = build_http_client(app_base_url, inp.agent_token, timeout=limits.http_timeout_s, transport=transport)
    deps = AppDeps(
        http=http, user=inp.user, today=inp.today, weekday=inp.weekday, code_budget_s=limits.code_max_duration_s,
    )
    try:
        try:  # thành viên lấy 1 lần đầu lượt; lỗi (kể cả 401) thì chạy tiếp, tool sẽ tự báo lỗi
            deps.members = await load_members(deps)
        except ToolError as e:
            deps.members_error = str(e)

        history = load_history(inp.history)
        usage = RunUsage()
        agent = build_agent(model, limits)
        try:
            result = await agent.run(
                inp.message, deps=deps, message_history=history, usage=usage,
                usage_limits=UsageLimits(request_limit=limits.request_limit),
            )
        except UsageLimitExceeded:
            messages = [*history, *_synthetic(inp.message, MSG_TOO_COMPLEX)]
            return TurnResult("answer", MSG_TOO_COMPLEX, _dump_history(messages, limits), _usage_dict(usage))
        except UnexpectedModelBehavior as e:
            if not _is_retry_exhaustion(e):
                raise  # ContentFilterError, phản hồi rỗng/sai định dạng… = lỗi provider → 502, Node fallback
            # Model không làm nổi (vd. run_code lỗi quá 3 lần, hay khẳng định "đã làm" mãi): trả lời thân thiện,
            # không phải 502 — 502 dành cho lỗi thật của LLM/endpoint. Chỉ log tên lớp.
            log.warning(json.dumps({"event": "model_gave_up", "error": type(e).__name__}))
            messages = [*history, *_synthetic(inp.message, MSG_GAVE_UP)]
            return TurnResult("answer", MSG_GAVE_UP, _dump_history(messages, limits), _usage_dict(usage))

        kind, reply, operations, question, options = settle(deps, result.output)
        messages = list(result.all_messages())
        if kind != "answer" or result.output is None:
            # Lượt kết thúc không qua câu trả lời của model: ghi lời dẫn người dùng đã thấy để lượt sau có ngữ cảnh.
            messages.append(ModelResponse(parts=[TextPart(reply)]))
        return TurnResult(
            kind, reply, _dump_history(messages, limits), _usage_dict(result.usage),
            operations=operations, question=question, options=options,
        )
    finally:
        await deps.aclose()
