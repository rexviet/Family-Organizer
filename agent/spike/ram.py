"""RAM probe: idle RSS vs RSS/peak (VmHWM) after a run with 5 tool calls. Mac arm64 container, not Pi."""
import asyncio, time
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai_harness import CodeMode
import pydantic_ai.models.openai  # noqa: F401  (loaded in real agent)


def mem():
    d = {}
    for l in open('/proc/self/status'):
        if l.startswith(('VmRSS', 'VmHWM')):
            k, v = l.split(':'); d[k] = int(v.split()[0]) // 1024
    return d


CODE = """
import asyncio
a = await asyncio.gather(*[list_items(n=i) for i in range(5)])
sum(len(x) for x in a)
"""
n = {'i': 0}
def fn(messages, info):
    n['i'] += 1
    if n['i'] % 2 == 1:
        return ModelResponse(parts=[ToolCallPart('run_code', {'code': CODE})])
    return ModelResponse(parts=[TextPart('ok')])

agent = Agent(FunctionModel(fn), capabilities=[CodeMode()])

@agent.tool_plain
async def list_items(n: int) -> list[dict]:
    """list items"""
    await asyncio.sleep(0.2)
    return [{'id': i, 'name': 'x' * 40, 'n': n} for i in range(200)]

print('import-only', mem(), flush=True)
time.sleep(6)  # idle window for docker stats
print('idle', mem(), flush=True)
agent.run_sync('go')  # warm-up (first Monty pool)
print('after run 1', mem(), flush=True)
t = time.time()
for _ in range(20):
    agent.run_sync('go')
print('after 20 runs', mem(), f'{(time.time()-t)/20:.2f}s/run', flush=True)
time.sleep(4)
