"""Requirement 4 harness: 10 Vietnamese questions x fake tools x one OpenAI-compatible endpoint.

  AGENT_LLM_BASE_URL=... AGENT_LLM_API_KEY=... AGENT_LLM_MODEL=... python eval_quality.py
  python eval_quality.py --selftest     # plumbing check with a scripted model, no LLM

Docker: docker run --rm --env-file .env agent-spike python eval_quality.py
Ollama: AGENT_LLM_BASE_URL=http://localhost:11434/v1 AGENT_LLM_API_KEY=ollama AGENT_LLM_MODEL=<tool-capable model>
(from a container on Mac use host.docker.internal instead of localhost)
"""
import os, sys, time, unicodedata
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, CallToolsNode, ModelRequestNode, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.result import FinalResult
from pydantic_ai.usage import UsageLimits
from pydantic_graph import End
from pydantic_ai_harness import CodeMode

TODAY = '2026-10-10'
MEMBERS = [
    {'id': 'm1', 'name': 'Bố Minh', 'role': 'parent'},
    {'id': 'm2', 'name': 'Mẹ Lan', 'role': 'parent'},
    {'id': 'm3', 'name': 'Bé Na', 'role': 'child'},
    {'id': 'm4', 'name': 'Bé Bin', 'role': 'child'},
]
TASKS = [
    {'id': 't1', 'title': 'Đánh răng', 'assignee': 'm3', 'due': '2026-10-10', 'done': False},
    {'id': 't2', 'title': 'Làm bài tập toán', 'assignee': 'm3', 'due': '2026-10-10', 'done': False},
    {'id': 't3', 'title': 'Dọn phòng', 'assignee': 'm3', 'due': '2026-10-11', 'done': False},
    {'id': 't4', 'title': 'Cho mèo ăn', 'assignee': 'm4', 'due': '2026-10-10', 'done': True},
    {'id': 't5', 'title': 'Đóng tiền điện', 'assignee': 'm2', 'due': '2026-10-12', 'done': False},
    {'id': 't6', 'title': 'Họp phụ huynh', 'assignee': 'm2', 'due': '2026-10-14', 'done': False},
    {'id': 't7', 'title': 'Sửa vòi nước', 'assignee': 'm1', 'due': '2026-10-20', 'done': False},
]
SHOPPING = [
    {'id': 's1', 'name': 'Sữa tươi', 'qty': '2 hộp', 'bought': False},
    {'id': 's2', 'name': 'Gạo', 'qty': '5 kg', 'bought': True},
    {'id': 's3', 'name': 'Dầu ăn', 'qty': '1 chai', 'bought': False},
]

INSTRUCTIONS = f"""Bạn là trợ lý gia đình. Trả lời ngắn, tiếng Việt.
Hôm nay là {TODAY} (thứ Bảy), múi giờ Asia/Ho_Chi_Minh.
Muốn thay đổi dữ liệu PHẢI gọi propose_add_shopping_items, không được nói là đã làm.
Nếu yêu cầu mơ hồ (thiếu đối tượng/nội dung) hãy hỏi lại người dùng bằng một câu hỏi, đừng đoán và đừng gọi propose."""


@dataclass
class Deps:
    proposals: list = field(default_factory=list)


@dataclass
class EndWhenSettled(AbstractCapability[Deps]):
    async def after_node_run(self, ctx: RunContext[Deps], *, node: Any, result: Any) -> Any:
        if not isinstance(node, CallToolsNode) or isinstance(result, End) or not ctx.deps.proposals:
            return result
        if isinstance(result, ModelRequestNode):
            ctx.messages.append(result.request)
        return End(FinalResult(None))


def build_agent(model) -> Agent:
    agent = Agent(model, deps_type=Deps, instructions=INSTRUCTIONS,
                  capabilities=[CodeMode(resource_limits={'max_duration_secs': 15, 'max_memory': 128 * 1024 * 1024}),
                                EndWhenSettled()])

    @agent.tool_plain
    def list_members() -> list[dict]:
        """List family members: id, name, role (parent|child)."""
        return MEMBERS

    @agent.tool_plain
    def list_tasks(assignee_id: str | None = None, due: str | None = None) -> list[dict]:
        """List tasks (id, title, assignee member id, due YYYY-MM-DD, done). Optional filters."""
        return [t for t in TASKS if (assignee_id is None or t['assignee'] == assignee_id)
                and (due is None or t['due'] == due)]

    @agent.tool_plain
    def list_shopping() -> list[dict]:
        """List shopping list items (id, name, qty, bought)."""
        return SHOPPING

    @agent.tool
    def propose_add_shopping_items(ctx: RunContext[Deps], items: list[str]) -> str:
        """Propose adding items (names) to the shopping list. Needs user approval; nothing is written."""
        ctx.deps.proposals.append(items)
        return 'proposal recorded'
    return agent


def norm(s: str) -> str:
    return unicodedata.normalize('NFC', s).lower()


def has(text: str, *words: str) -> bool:
    t = norm(text)
    return all(norm(w) in t for w in words)


# (question, kind, checker(output_text, proposals) -> bool)
CASES = [
    ('Hôm nay bé Na có những việc gì?', 'read', lambda o, p: has(o, 'đánh răng', 'toán') and not p),
    ('Ai đang có nhiều việc chưa xong nhất?', 'read', lambda o, p: has(o, 'na') and not p),
    ('Trong danh sách đi chợ còn thiếu gì?', 'read', lambda o, p: has(o, 'sữa', 'dầu') and not has(o, 'gạo') and not p),
    ('Nhà mình có mấy thành viên và ai là trẻ em?', 'read', lambda o, p: has(o, '4', 'na', 'bin') and not p),
    ('Việc nào của mẹ Lan hạn trong tuần này?', 'read', lambda o, p: has(o, 'tiền điện') and not p),
    ('Thêm sữa chua và 2 chục trứng vào danh sách đi chợ', 'propose',
     lambda o, p: len(p) == 1 and has(' '.join(p[0]), 'sữa chua') and has(' '.join(p[0]), 'trứng')),
    ('Mai đi chợ nhớ mua rau muống với cà chua giúp mình', 'propose',
     lambda o, p: len(p) == 1 and has(' '.join(p[0]), 'rau muống') and has(' '.join(p[0]), 'cà chua')),
    ('Danh sách đã có sữa tươi rồi, thêm bột giặt và nước rửa chén nhé', 'propose',
     lambda o, p: len(p) == 1 and has(' '.join(p[0]), 'bột giặt', 'nước rửa chén') and not has(' '.join(p[0]), 'sữa tươi')),
    ('Thêm cái đó vào danh sách nhé', 'ambiguous', lambda o, p: not p and '?' in o),
    ('Giao việc cho bé', 'ambiguous', lambda o, p: not p and '?' in o),
]


def run_case(agent: Agent, q: str):
    deps = Deps()
    t = time.time()
    try:
        r = agent.run_sync(q, deps=deps, usage_limits=UsageLimits(request_limit=6))
        return (r.output or ''), deps.proposals, r.usage.requests, time.time() - t, None
    except Exception as e:  # report odd 400s verbatim
        return '', deps.proposals, 0, time.time() - t, f'{type(e).__name__}: {str(e)[:160]}'


def main() -> int:
    if '--selftest' in sys.argv:
        from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
        from pydantic_ai.models.function import FunctionModel
        step = {'n': 0}

        def fn(messages, info):
            step['n'] += 1
            if step['n'] % 2 == 1:
                return ModelResponse(parts=[ToolCallPart('run_code', {'code': 'await list_members()'})])
            return ModelResponse(parts=[TextPart('4 thành viên: Na, Bin là trẻ em?')])
        model = FunctionModel(fn)
        name = 'selftest'
    else:
        need = ['AGENT_LLM_BASE_URL', 'AGENT_LLM_API_KEY', 'AGENT_LLM_MODEL']
        if any(not os.environ.get(k) for k in need):
            print('SKIP live run: set', ', '.join(need))
            return 0
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        name = os.environ['AGENT_LLM_MODEL']
        model = OpenAIChatModel(name, provider=OpenAIProvider(
            base_url=os.environ['AGENT_LLM_BASE_URL'], api_key=os.environ['AGENT_LLM_API_KEY']))
    agent = build_agent(model)
    rows, passed = [], 0
    for q, kind, check in CASES:
        out, props, reqs, dt, err = run_case(agent, q)
        ok = err is None and check(out, props)
        passed += ok
        rows.append((q, kind, 'PASS' if ok else 'FAIL', reqs, dt, err or out[:60].replace('\n', ' ') or f'proposal={props}'))
    print(f'model={name}')
    print(f'{"question":58} {"kind":9} {"res":4} {"req":3} {"sec":>5}  note')
    for q, kind, res, reqs, dt, note in rows:
        print(f'{q[:58]:58} {kind:9} {res:4} {reqs:3} {dt:5.1f}  {note}')
    print(f'TOTAL {passed}/{len(CASES)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
