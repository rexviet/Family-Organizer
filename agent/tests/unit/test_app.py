"""/health và /run: xác thực, cấu hình, validate, giới hạn, log — model thật được thay bằng TestModel/FunctionModel."""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from family_agent.app import create_app
from family_agent.contract import CONTRACT_VERSION
from family_agent.settings import Settings
from tests.conftest import SECRET, build_settings

pytestmark = pytest.mark.anyio

TOKEN = "agent-token-KHONG-DUOC-LO-123456"
API_KEY = "sk-llm-key-KHONG-DUOC-LO"
BASE_URL = "http://llm-noi-bo.local/v1"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_settings(**kw: Any) -> Settings:
    base: dict[str, Any] = {
        "shared_secret": SECRET, "llm_base_url": BASE_URL, "llm_api_key": API_KEY,
        "llm_model": "kr/deepseek-3.2", "version": "1.2.3",
        "code_max_duration_s": 0.04,  # 2× phải < run_timeout_s; các test timeout đặt run_timeout_s rất nhỏ
    }
    s: Settings = build_settings(**(base | kw))
    return s


def body(**kw: Any) -> dict[str, Any]:
    b: dict[str, Any] = {
        "message": "Hôm nay nhà mình có việc gì?",
        "history": [],
        "user": {"id": "user_me", "fullName": "Mẹ Lan", "role": "member"},
        "agentToken": TOKEN,
        "today": "2026-10-10",
        "weekday": "Thứ Bảy",
    }
    return b | kw


@pytest.fixture
def client_for() -> Callable[..., Any]:
    """client_for(settings, model) → AsyncClient gắn app qua ASGITransport."""

    def make(settings: Settings | None = None, model: Model | None = None) -> httpx.AsyncClient:
        m = model or TestModel(custom_output_text="Hôm nay có 2 việc.", call_tools=[])
        app = create_app(
            settings or make_settings(), model_factory=lambda _s: m,
            http_transport=httpx.MockTransport(lambda _r: httpx.Response(200, json={"users": []})),  # giả app Node
        )
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")

    return make


H = {"X-Agent-Secret": SECRET}


# --- /health -----------------------------------------------------------------

async def test_health_da_cau_hinh(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for() as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json() == {
        "ok": True, "llmConfigured": True, "model": "kr/deepseek-3.2",
        "version": "1.2.3", "contractVersion": CONTRACT_VERSION,
    }
    assert API_KEY not in r.text and BASE_URL not in r.text and SECRET not in r.text


async def test_health_chua_cau_hinh_llm(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for(make_settings(llm_api_key="")) as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["llmConfigured"] is False
    assert r.json()["model"] is None


# --- chỉ có 2 endpoint ---------------------------------------------------------

@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/"])
async def test_khong_co_endpoint_khac(client_for: Callable[..., httpx.AsyncClient], path: str) -> None:
    async with client_for() as c:
        r = await c.get(path)
    assert r.status_code == 404


# --- /run: xác thực ---------------------------------------------------------------

@pytest.mark.parametrize("headers", [{}, {"X-Agent-Secret": "sai"}, {"X-Agent-Secret": SECRET + "x"}])
async def test_run_secret_sai_401(client_for: Callable[..., httpx.AsyncClient], headers: dict[str, str]) -> None:
    async with client_for() as c:
        r = await c.post("/run", json=body(), headers=headers)
    assert r.status_code == 401


async def test_run_secret_sai_kiem_truoc_body(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for() as c:
        r = await c.post("/run", content=b"khong phai json", headers={"X-Agent-Secret": "sai"})
    assert r.status_code == 401


async def test_run_secret_khong_ascii_401(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for() as c:
        r = await c.post("/run", json=body(), headers={"X-Agent-Secret": "mật-khẩu".encode()})
    assert r.status_code == 401


# --- /run: cấu hình LLM ------------------------------------------------------------

async def test_run_chua_cau_hinh_llm_503(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for(make_settings(llm_model="")) as c:
        r = await c.post("/run", json=body(), headers=H)
    assert r.status_code == 503
    assert r.json()["error"] == "llm_not_configured"


# --- /run: body sai → 422 không lộ token --------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        body(message=""),
        body(user={"id": "u", "fullName": "x", "role": "boss"}),
        body(today="10/10/2026"),
        body(today="2026-10-10\n"),
        body(agentToken=12345),
        body(history="khong-phai-mang"),
        {k: v for k, v in body().items() if k != "agentToken"},
        body(message=TOKEN * 1000),
        [body()],
    ],
)
async def test_run_body_sai_422_khong_echo(
    client_for: Callable[..., httpx.AsyncClient], payload: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    async with client_for() as c:
        r = await c.post("/run", json=payload, headers=H)
    assert r.status_code == 422
    data = r.json()
    assert data["error"] == "invalid_request"
    assert TOKEN not in r.text
    for e in data["errors"]:
        assert set(e) <= {"loc", "msg", "type"}
    assert TOKEN not in caplog.text


async def test_run_json_hong_422(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for() as c:
        r = await c.post("/run", content=b'{"agentToken": "' + TOKEN.encode() + b'"', headers=H)
    assert r.status_code == 422
    assert TOKEN not in r.text


async def test_run_body_qua_lon_413(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for(make_settings(max_body_bytes=1000)) as c:
        r = await c.post("/run", json=body(message="a" * 2000), headers=H)
    assert r.status_code == 413


# --- /run: thành công ------------------------------------------------------------------

async def test_run_tra_answer(client_for: Callable[..., httpx.AsyncClient], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    async with client_for() as c:
        r = await c.post("/run", json=body(), headers=H)
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "answer"
    assert data["reply"] == "Hôm nay có 2 việc."
    assert data["contractVersion"] == CONTRACT_VERSION
    assert isinstance(data["history"], list) and len(data["history"]) == 2
    assert data["usage"]["requests"] == 1
    assert set(data["usage"]) == {"requests", "toolCalls", "inputTokens", "outputTokens"}
    assert TOKEN not in r.text and TOKEN not in caplog.text

    # Đúng một dòng log JSON cho lượt, không có nội dung hội thoại.
    lines = [rec.getMessage() for rec in caplog.records if rec.name == "family_agent.run"]
    assert len(lines) == 1
    log = json.loads(lines[0])
    assert log["event"] == "run" and log["status"] == 200 and log["kind"] == "answer"
    assert log["userId"] == "user_me"
    assert {"ms", "requests", "toolCalls", "inputTokens", "outputTokens"} <= set(log)
    assert "Hôm nay" not in caplog.text and "Mẹ Lan" not in caplog.text


async def test_run_dung_history_cu(client_for: Callable[..., httpx.AsyncClient]) -> None:
    seen: list[int] = []

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(len(messages))
        return ModelResponse(parts=[TextPart("ok")])

    async with client_for(model=FunctionModel(fn)) as c:
        r1 = await c.post("/run", json=body(), headers=H)
        r2 = await c.post("/run", json=body(history=r1.json()["history"]), headers=H)
    assert r2.status_code == 200
    assert seen == [1, 3]
    assert len(r2.json()["history"]) == 4


async def test_run_history_khong_doc_duoc_thi_bo_qua(client_for: Callable[..., httpx.AsyncClient]) -> None:
    async with client_for() as c:
        r = await c.post("/run", json=body(history=[{"kind": "la-lam", "parts": 1}]), headers=H)
    assert r.status_code == 200
    assert len(r.json()["history"]) == 2


# --- /run: lỗi model, timeout, đồng thời ---------------------------------------------------

async def test_run_loi_model_502_khong_lo_chi_tiet(
    client_for: Callable[..., httpx.AsyncClient], caplog: pytest.LogCaptureFixture
) -> None:
    def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError(f"upstream {BASE_URL} từ chối key {API_KEY}")

    async with client_for(model=FunctionModel(boom)) as c:
        r = await c.post("/run", json=body(), headers=H)
    assert r.status_code == 502
    assert r.json()["error"] == "llm_error"
    assert API_KEY not in r.text and BASE_URL not in r.text
    assert API_KEY not in caplog.text and TOKEN not in caplog.text


def blocking_model(started: asyncio.Event, release: asyncio.Event) -> FunctionModel:
    async def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        started.set()
        await release.wait()
        return ModelResponse(parts=[TextPart("xong")])

    return FunctionModel(fn)


async def test_run_qua_timeout_504(client_for: Callable[..., httpx.AsyncClient]) -> None:
    model = blocking_model(asyncio.Event(), asyncio.Event())
    async with client_for(make_settings(run_timeout_s=0.2), model) as c:
        r = await c.post("/run", json=body(), headers=H)
    assert r.status_code == 504
    assert r.json()["error"] == "timeout"


async def test_run_day_slot_429_ngay(client_for: Callable[..., httpx.AsyncClient]) -> None:
    started, release = asyncio.Event(), asyncio.Event()
    model = blocking_model(started, release)
    async with client_for(make_settings(max_concurrent_runs=1), model) as c:
        first = asyncio.create_task(c.post("/run", json=body(), headers=H))
        await asyncio.wait_for(started.wait(), 2)
        r = await asyncio.wait_for(c.post("/run", json=body(), headers=H), 1)
        assert r.status_code == 429
        assert r.json()["error"] == "busy"
        release.set()
        assert (await first).status_code == 200
        # Slot được trả lại sau khi lượt đầu xong.
        r3 = await c.post("/run", json=body(), headers=H)
        assert r3.status_code == 200


async def test_slot_tra_lai_sau_loi(client_for: Callable[..., httpx.AsyncClient]) -> None:
    model = blocking_model(asyncio.Event(), asyncio.Event())
    async with client_for(make_settings(max_concurrent_runs=1, run_timeout_s=0.1), model) as c:
        assert (await c.post("/run", json=body(), headers=H)).status_code == 504
        assert (await c.post("/run", json=body(), headers=H)).status_code == 504  # không phải 429




async def test_timeout_ben_trong_model_la_502_khong_phai_504(client_for: Callable[..., httpx.AsyncClient]) -> None:
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise TimeoutError("read timeout từ httpx")

    async with client_for(model=FunctionModel(fn)) as c:
        r = await c.post("/run", json=body(), headers=H)
    assert r.status_code == 502


async def test_huy_luot_tra_slot(
    client_for: Callable[..., httpx.AsyncClient], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    started, release = asyncio.Event(), asyncio.Event()
    async with client_for(make_settings(max_concurrent_runs=1), blocking_model(started, release)) as c:
        task = asyncio.create_task(c.post("/run", json=body(), headers=H))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        assert (await c.post("/run", json=body(), headers=H)).status_code == 200
    statuses = [json.loads(r.getMessage()).get("status") for r in caplog.records if r.name == "family_agent.run"]
    assert 499 in statuses


async def test_tu_choi_vi_ban_co_log(
    client_for: Callable[..., httpx.AsyncClient], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    started, release = asyncio.Event(), asyncio.Event()
    async with client_for(make_settings(max_concurrent_runs=1), blocking_model(started, release)) as c:
        first = asyncio.create_task(c.post("/run", json=body(), headers=H))
        await asyncio.wait_for(started.wait(), 2)
        assert (await c.post("/run", json=body(), headers=H)).status_code == 429
        release.set()
        await first
    logs = [json.loads(r.getMessage()) for r in caplog.records if r.name == "family_agent.run"]
    assert {"event": "rejected", "status": 429} in logs


async def test_client_ngat_khi_dang_gui_body() -> None:
    app = create_app(make_settings(), model_factory=lambda _s: TestModel())
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(msg: dict[str, Any]) -> None:
        sent.append(msg)

    scope = {
        "type": "http", "method": "POST", "path": "/run", "raw_path": b"/run", "query_string": b"",
        "headers": [(b"x-agent-secret", SECRET.encode())], "http_version": "1.1", "scheme": "http",
        "server": ("agent", 80), "client": ("app", 1), "root_path": "",
    }
    await app(scope, receive, send)  # không được ném lỗi (uvicorn sẽ log traceback)
    assert sent and sent[0]["status"] == 400


# --- /run: harness thật (3 kind) ----------------------------------------------------------------------

def app_mock(seen: list[httpx.Request]) -> httpx.MockTransport:
    """Giả app Node: ghi lại mọi request để chứng minh agent chỉ GET."""
    data = {
        "/api/users": {"users": [{"id": "user_me", "fullName": "Mẹ Lan", "role": "member", "familyRelation": "me"}]},
        "/api/shopping": {"shoppingItems": []},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=data.get(request.url.path, {}))

    return httpx.MockTransport(handler)


def code_call(src: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("run_code", {"code": src})])


def app_client(model: Model, transport: httpx.MockTransport, settings: Settings | None = None) -> httpx.AsyncClient:
    app = create_app(settings or make_settings(), model_factory=lambda _s: model, http_transport=transport)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://agent")


async def test_run_tra_proposal_chi_get_va_khong_lo_token() -> None:
    seen: list[httpx.Request] = []
    model = FunctionModel(lambda _m, _i: code_call("await propose_add_shopping_items(items=['Sữa chua'])"))
    async with app_client(model, app_mock(seen)) as c:
        r = await c.post("/run", json=body(message="thêm sữa chua"), headers=H)
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "proposal"
    assert data["operations"] == [{"type": "shopping.add", "items": [{"name": "Sữa chua"}]}]
    assert data["reply"] == "Mình đề xuất 1 thay đổi — bạn xem và bấm Duyệt nhé."
    assert "question" not in data and data["usage"]["requests"] == 1
    assert TOKEN not in r.text
    assert {q.method for q in seen} == {"GET"}
    assert all(q.headers["authorization"] == f"Bearer {TOKEN}" for q in seen)


async def test_run_tra_clarification() -> None:
    ask = "await ask_user(question='Giao cho bé nào?', options=['Na', 'Bin'])"
    model = FunctionModel(lambda _m, _i: code_call(ask))
    async with app_client(model, app_mock([])) as c:
        r = await c.post("/run", json=body(message="giao việc cho bé"), headers=H)
    data = r.json()
    assert (data["kind"], data["question"], data["options"]) == ("clarification", "Giao cho bé nào?", ["Na", "Bin"])
    assert data["reply"] == "Giao cho bé nào?" and "operations" not in data


async def test_run_code_chay_vo_han_bi_chan_boi_gioi_han_va_health_van_tra_loi() -> None:
    """Phát hiện phase 4: Monty chạy ĐỒNG BỘ trên event loop → /health (và mọi lượt khác) bị treo tới khi hết
    `max_duration_secs`; sau đó Monty báo lỗi cho model và lượt cứ thế tiếp tục (ở đây model ngủ → timeout 504)."""
    steps = iter([code_call("while True:\n    pass"), None])

    async def fn(_m: list[ModelMessage], _i: AgentInfo) -> ModelResponse:
        step = next(steps)
        if step is None:
            await asyncio.sleep(5)  # sau khi Monty ngắt, lượt chờ ở điểm await → timeout cứng cắt được
        assert step is not None
        return step

    code_limit, run_limit = 0.4, 1.0
    settings = make_settings(run_timeout_s=run_limit, code_max_duration_s=code_limit)
    gaps: list[float] = []

    async def ticker(stop: asyncio.Event) -> None:
        last = time.monotonic()
        while not stop.is_set():
            await asyncio.sleep(0.02)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    stop = asyncio.Event()
    async with app_client(FunctionModel(fn), app_mock([]), settings) as c:
        tick = asyncio.create_task(ticker(stop))
        await asyncio.sleep(0)  # để ticker chạy một nhịp
        started = time.monotonic()
        run_task = asyncio.create_task(c.post("/run", json=body(), headers=H))
        health_task = asyncio.create_task(c.get("/health"))
        health = await asyncio.wait_for(health_task, code_limit + 1.5)
        health_after = time.monotonic() - started
        r = await asyncio.wait_for(run_task, run_limit + 1.5)
        run_after = time.monotonic() - started
        stop.set()
        await tick
    assert health.status_code == 200
    assert r.status_code == 504
    assert max(gaps) >= code_limit * 0.8, "Monty không còn chạy đồng bộ? Cập nhật ghi chú phase 4 nếu đúng vậy"
    assert max(gaps) <= code_limit + 0.5  # treo tối đa ≈ max_duration, không hơn
    assert health_after <= code_limit + 1.0
    assert run_after <= run_limit + 1.0


async def test_model_viet_code_loi_mai_van_tra_answer_than_thien_khong_502() -> None:
    """run_code có ngưỡng retry riêng (3) → UnexpectedModelBehavior → answer thân thiện (không 502)."""
    model = FunctionModel(lambda _m, _i: code_call("1 +"))
    async with app_client(model, app_mock([])) as c:
        r = await c.post("/run", json=body(), headers=H)
    assert r.status_code == 200 and r.json()["kind"] == "answer"
    assert TOKEN not in r.text
