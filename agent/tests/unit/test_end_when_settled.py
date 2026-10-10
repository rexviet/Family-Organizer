"""EndWhenSettled: có đề xuất hoặc câu hỏi → kết thúc lượt ngay, KHÔNG gửi request model thứ 2."""

from collections.abc import AsyncIterator

import pytest
import respx
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness import CodeMode

from family_agent.harness.deps import AppDeps, UserInfo, build_http_client
from family_agent.harness.end_when_settled import EndWhenSettled, is_settled
from family_agent.harness.tools.ask import ask_toolset
from family_agent.harness.tools.read import read_toolset
from family_agent.harness.tools.shopping import shopping_toolset

pytestmark = pytest.mark.anyio

BASE = "http://app.test:3000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def deps() -> AsyncIterator[AppDeps]:
    http = build_http_client(BASE, "tok-123")
    yield AppDeps(http=http, user=UserInfo("u", "Mẹ Lan", "member"), today="2026-10-10", weekday="Thứ Bảy")
    await http.aclose()


def code(src: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("run_code", {"code": src})])


def script(*steps: ModelResponse) -> tuple[FunctionModel, list[int]]:
    calls: list[int] = []

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(len(messages))
        return steps[min(len(calls), len(steps)) - 1]

    return FunctionModel(fn), calls


def make_agent(model: FunctionModel) -> Agent[AppDeps, str]:
    return Agent(
        model, deps_type=AppDeps, toolsets=[read_toolset, shopping_toolset, ask_toolset],
        capabilities=[CodeMode(), EndWhenSettled()],
    )


async def test_is_settled_theo_outcome_hoac_cau_hoi(deps: AppDeps) -> None:
    assert not is_settled(deps)
    deps.clarifications.ask("Ai?")
    assert is_settled(deps)
    d2 = AppDeps(http=deps.http, user=deps.user, today=deps.today, weekday=deps.weekday)
    d2.outcome.add({"type": "shopping.add", "items": [{"name": "A"}]})
    assert is_settled(d2)


async def test_co_de_xuat_thi_ket_thuc_sau_1_request(deps: AppDeps) -> None:
    model, calls = script(
        code("await propose_add_shopping_items(items=['Sữa chua'])"),
        ModelResponse(parts=[TextPart("KHÔNG ĐƯỢC TỚI ĐÂY")]),
    )
    with respx.mock:
        respx.get(f"{BASE}/api/shopping").respond(json={"shoppingItems": []})
        result = await make_agent(model).run("thêm sữa chua", deps=deps, usage_limits=UsageLimits(request_limit=6))
    assert len(calls) == 1
    assert result.output is None
    assert deps.outcome.operations == [{"type": "shopping.add", "items": [{"name": "Sữa chua"}]}]
    last = result.all_messages()[-1]
    assert last.parts[0].part_kind == "tool-return"  # lịch sử không để tool call mồ côi
    assert result.usage.requests == 1


async def test_co_cau_hoi_thi_ket_thuc_sau_1_request(deps: AppDeps) -> None:
    model, calls = script(code("await ask_user(question='Giao việc cho ai?', options=['Na', 'Bin'])"), code("1"))
    result = await make_agent(model).run("giao việc cho bé", deps=deps)
    assert len(calls) == 1
    assert result.output is None
    first = deps.clarifications.first()
    assert first is not None and first.options == ("Na", "Bin")


async def test_chi_doc_thi_van_tiep_tuc_den_cau_tra_loi(deps: AppDeps) -> None:
    model, calls = script(code("await list_shopping()"), ModelResponse(parts=[TextPart("Chưa có gì cần mua.")]))
    with respx.mock:
        respx.get(f"{BASE}/api/shopping").respond(json={"shoppingItems": []})
        result = await make_agent(model).run("còn thiếu gì?", deps=deps)
    assert len(calls) == 2
    assert result.output == "Chưa có gì cần mua."
    assert deps.outcome.is_empty() and deps.clarifications.is_empty()


async def test_lich_su_ket_thuc_bang_tool_return_van_noi_tiep_duoc(deps: AppDeps) -> None:
    model, _ = script(code("await ask_user(question='Ai?')"))
    first = await make_agent(model).run("giao việc", deps=deps)
    seen: list[list[ModelMessage]] = []

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(messages)
        return ModelResponse(parts=[TextPart("ok")])

    d2 = AppDeps(http=deps.http, user=deps.user, today=deps.today, weekday=deps.weekday)
    follow_up: Agent[AppDeps, str] = Agent(FunctionModel(fn), deps_type=AppDeps)
    second = await follow_up.run("cho Na", message_history=first.all_messages(), deps=d2)
    assert second.output == "ok"
    assert len(seen) == 1 and len(seen[0]) >= 3


async def test_ghi_nhan_nhieu_ket_qua_trong_cung_buoc(deps: AppDeps) -> None:
    model, calls = script(code(
        "import asyncio\n"
        "await asyncio.gather(ask_user(question='Ai?'), propose_add_shopping_items(items=['A']))"
    ))
    with respx.mock:
        respx.get(f"{BASE}/api/shopping").respond(json={"shoppingItems": []})
        await make_agent(model).run("x", deps=deps)
    assert len(calls) == 1
    assert not deps.clarifications.is_empty() and not deps.outcome.is_empty()
