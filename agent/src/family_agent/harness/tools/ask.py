"""Tool hỏi lại: `ask_user` (spec §6.3). Câu hỏi do tool ghi, `/run` trả đúng chữ đó cho người dùng."""

from __future__ import annotations

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from family_agent.harness.clarify import ClarificationError
from family_agent.harness.deps import AppDeps, ToolError, flag_failures

STOP_MESSAGE = "Đã gửi câu hỏi cho người dùng. Hãy DỪNG: không gọi thêm tool, không trả lời thêm."


async def ask_user(ctx: RunContext[AppDeps], question: str, options: list[str] | None = None) -> str:
    """Hỏi lại người dùng khi yêu cầu MƠ HỒ hoặc thiếu thông tin (không đoán, không đề xuất bừa).

    Gọi xong là kết thúc lượt; câu trả lời của người dùng sẽ đến ở tin nhắn kế tiếp.

    Args:
        question: MỘT câu hỏi ngắn, tiếng Việt, rõ người dùng cần trả lời điều gì.
        options: (tuỳ chọn) tối đa 10 lựa chọn ngắn để người dùng bấm, ví dụ ["Lan", "Bà ngoại"].
    """
    with flag_failures(ctx.deps):
        try:
            ctx.deps.clarifications.ask(question, options or [])
        except ClarificationError as e:
            raise ToolError(str(e)) from None
    return STOP_MESSAGE


ask_toolset: FunctionToolset[AppDeps] = FunctionToolset([ask_user])
