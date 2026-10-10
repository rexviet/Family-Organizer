"""Spike S1 offline checks (no LLM). Run: python checks.py"""
import asyncio, json, sys, time, platform
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, CallToolsNode, ModelRequestNode, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import (ModelMessage, ModelMessagesTypeAdapter, ModelResponse,
                                  TextPart, ToolCallPart)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.result import FinalResult
from pydantic_ai.usage import UsageLimits
from pydantic_graph import End
from pydantic_ai_harness import CodeMode

print("platform:", platform.machine(), sys.version.split()[0])
RESULTS: dict[str, str] = {}


def run_code(code: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart('run_code', {'code': code})])


def text(t: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(t)])


def scripted(*steps: ModelResponse, log: list | None = None):
    it = iter(steps)

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if log is not None:
            log.append(info)
        return next(it)
    return FunctionModel(fn)


# --- 1. basic CodeMode example ---
def check_basic():
    infos: list[AgentInfo] = []
    m = scripted(
        run_code("import asyncio\na, b = await asyncio.gather(get_weather(city='Paris'), get_weather(city='Tokyo'))\n{'p': a['temp_f'], 't': b['temp_f']}"),
        text('done'), log=infos)
    agent = Agent(m, capabilities=[CodeMode()])

    @agent.tool_plain
    def get_weather(city: str) -> dict:
        """Get weather."""
        return {'city': city, 'temp_f': 72}

    r = agent.run_sync('weather?')
    names = [t.name for t in infos[0].function_tools]
    tool_ret = [p for msg in r.all_messages() for p in msg.parts if p.part_kind == 'tool-return']
    print('tools shown to model:', names)
    print('run_code return:', tool_ret[0].content)
    assert names == ['run_code'], names
    assert tool_ret[0].content == {'p': 72, 't': 72} or '72' in str(tool_ret[0].content)
    RESULTS['basic'] = 'PASS'


# --- 2. EndWhenSettled ---
@dataclass
class Deps:
    outcome: list = field(default_factory=list)


@dataclass
class EndWhenSettled(AbstractCapability[Deps]):
    async def after_node_run(self, ctx: RunContext[Deps], *, node: Any, result: Any) -> Any:
        if not isinstance(node, CallToolsNode) or isinstance(result, End):
            return result
        if not ctx.deps.outcome:
            return result
        if isinstance(result, ModelRequestNode):
            ctx.messages.append(result.request)
        return End(FinalResult(None))


def check_end_when_settled():
    calls = {'n': 0}

    def fn(messages, info):
        calls['n'] += 1
        if calls['n'] == 1:
            return run_code("await propose_add_shopping_items(items=['milk','eggs'])")
        return text('SHOULD NOT HAPPEN')

    agent = Agent(FunctionModel(fn), deps_type=Deps, capabilities=[CodeMode(), EndWhenSettled()],
                  output_type=[str, None] if False else str)

    @agent.tool
    def propose_add_shopping_items(ctx: RunContext[Deps], items: list[str]) -> str:
        """Record proposal."""
        ctx.deps.outcome.append({'op': 'add', 'items': items})
        return 'staged'

    deps = Deps()
    r = agent.run_sync('add milk', deps=deps, usage_limits=UsageLimits(request_limit=6))
    print('model requests:', calls['n'], 'outcome:', deps.outcome, 'output:', repr(r.output))
    assert calls['n'] == 1 and deps.outcome
    RESULTS['end_when_settled'] = f"PASS (requests={calls['n']}, output={r.output!r})"
    return r


# --- 3. resource limits ---
def _limit_case(code: str, **limits):
    agent = Agent(scripted(run_code(code), text('ok')),
                  capabilities=[CodeMode(resource_limits=limits)])

    @agent.tool_plain
    def noop() -> int:
        """noop"""
        return 1

    t = time.time()
    r = agent.run_sync('x')
    dt = time.time() - t
    rets = [p for m in r.all_messages() for p in m.parts if p.part_kind in ('tool-return', 'retry-prompt')]
    return dt, rets[0].content if rets else None


def check_limits():
    dt, out = _limit_case("i = 0\nwhile True:\n    i += 1", max_duration_secs=1.0)
    print(f'infinite loop: {dt:.2f}s ->', str(out)[:200])
    assert dt < 5 and 'time limit' in str(out).lower()
    RESULTS['limit_time'] = f'PASS ({dt:.2f}s, "{str(out)[:80]}")'
    dt, out = _limit_case("x = [0] * 200_000_000\nlen(x)", max_memory=32 * 1024 * 1024)
    print(f'big alloc: {dt:.2f}s ->', str(out)[:200])
    assert 'memory limit' in str(out).lower()
    RESULTS['limit_mem'] = f'PASS ({dt:.2f}s, "{str(out)[:80]}")'
    try:
        CodeMode(resource_limits={'max_duration_s': 1})  # wrong key
        agent = Agent(scripted(text('x')), capabilities=[CodeMode(resource_limits={'max_duration_s': 1})])
        agent.run_sync('x')
        RESULTS['limit_badkey'] = 'no error (!)'
    except Exception as e:
        RESULTS['limit_badkey'] = f'raises {type(e).__name__}: {str(e)[:100]}'


# --- 4. history round trip ---
def check_history():
    agent = Agent(scripted(text('one'), text('two')))
    r1 = agent.run_sync('hello')
    blob = ModelMessagesTypeAdapter.dump_json(r1.all_messages())
    hist = ModelMessagesTypeAdapter.validate_json(blob)
    seen = {}

    def fn(messages, info):
        seen['n'] = len(messages)
        return text('two')
    r2 = Agent(FunctionModel(fn)).run_sync('again', message_history=hist)
    print('history bytes', len(blob), 'msgs seen by 2nd run', seen['n'])
    assert seen['n'] == 3
    RESULTS['history'] = f'PASS ({len(blob)} B json, 2nd run saw {seen["n"]} msgs)'

    # with CodeMode tool call/return in the history
    agent = Agent(scripted(run_code('1+1'), text('done')), capabilities=[CodeMode()])
    r = agent.run_sync('calc')
    blob = ModelMessagesTypeAdapter.dump_json(r.all_messages())
    h = ModelMessagesTypeAdapter.validate_json(blob)
    agent2 = Agent(scripted(text('again')), capabilities=[CodeMode()])
    agent2.run_sync('more', message_history=h)
    RESULTS['history_codemode'] = 'PASS'


if __name__ == '__main__':
    for fn in (check_basic, check_end_when_settled, check_limits, check_history):
        try:
            fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            RESULTS[fn.__name__] = f'FAIL {type(e).__name__}: {e}'
    print(json.dumps(RESULTS, indent=1, ensure_ascii=False))
