"""AppDeps: client HTTP chỉ-GET + allowlist 9 endpoint, cache 1 lần/lượt, lỗi tiếng Việt, không lộ token."""

import asyncio
from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
import respx

from family_agent.harness.deps import ALLOWED_PATHS, AppApiError, AppDeps, UserInfo, build_http_client

pytestmark = pytest.mark.anyio

TOKEN = "agent-token-KHONG-DUOC-LO-123456"
BASE = "http://app.test:3000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def deps() -> AsyncIterator[AppDeps]:
    http = build_http_client(BASE, TOKEN)
    try:
        yield AppDeps(
            http=http, user=UserInfo("u1", "Mẹ Lan", "member"), today="2026-10-10", weekday="Thứ Bảy",
        )
    finally:
        await http.aclose()


def test_allowlist_dung_9_endpoint() -> None:
    assert sorted(ALLOWED_PATHS) == sorted([
        "/api/users", "/api/tasks", "/api/plans", "/api/finance", "/api/finance/categories",
        "/api/finance/budgets", "/api/finance/recurring-bills", "/api/shopping",
        "/api/shopping/meal-plan/current",
    ])


async def test_client_gui_bearer_va_timeout_10s() -> None:
    http = build_http_client(BASE, TOKEN)
    assert http.headers["Authorization"] == f"Bearer {TOKEN}"
    assert http.timeout.read == 10 and http.timeout.connect == 10
    assert str(http.base_url).rstrip("/") == BASE
    await http.aclose()


async def test_get_json_tra_du_lieu(deps: AppDeps) -> None:
    with respx.mock:
        route = respx.get(f"{BASE}/api/tasks").respond(json={"tasks": [{"id": "t1"}]})
        data = await deps.get_json("/api/tasks")
    assert data == {"tasks": [{"id": "t1"}]}
    assert route.calls.last.request.headers["authorization"] == f"Bearer {TOKEN}"


async def test_cache_moi_endpoint_toi_da_1_lan_ke_ca_goi_dong_thoi(deps: AppDeps) -> None:
    with respx.mock:
        route = respx.get(f"{BASE}/api/tasks").respond(json={"tasks": []})
        results = await asyncio.gather(*(deps.get_json("/api/tasks") for _ in range(5)))
        await deps.get_json("/api/tasks")
    assert route.call_count == 1
    assert all(r == {"tasks": []} for r in results)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
async def test_tu_choi_moi_method_khac_get(deps: AppDeps, method: str) -> None:
    with respx.mock:
        route = respx.route(host="app.test").respond(json={})
        with pytest.raises(AppApiError):
            await deps.http.request(method, "/api/tasks")
    assert route.call_count == 0


@pytest.mark.parametrize("path", [
    "/api/tasks/t1", "/api/users/u1", "/api/auth/me", "/api/tasks/", "/", "/api/shopping/purchased",
    "/api/tasks?x=1", "/api/finance/savings-goals",
])
async def test_tu_choi_path_ngoai_allowlist_hoac_co_query(deps: AppDeps, path: str) -> None:
    with respx.mock:
        route = respx.route(host="app.test").respond(json={})
        with pytest.raises(AppApiError):
            await deps.http.get(path)
    assert route.call_count == 0


async def test_tu_choi_host_khac_khong_gui_token_di_dau(deps: AppDeps) -> None:
    with respx.mock:
        route = respx.route().respond(json={})
        with pytest.raises(AppApiError):
            await deps.http.get("http://evil.example/api/tasks")
    assert route.call_count == 0


@pytest.mark.parametrize(("status", "needle"), [
    (401, "hết hạn"), (403, "không có quyền"), (404, "mã 404"), (500, "mã 500"), (302, "mã 302"),
])
async def test_loi_http_thanh_loi_tieng_viet_khong_lo_token(deps: AppDeps, status: int, needle: str) -> None:
    with respx.mock:
        respx.get(f"{BASE}/api/finance").respond(status, json={"error": f"chi tiết {TOKEN}"})
        with pytest.raises(AppApiError) as ei:
            await deps.get_json("/api/finance")
    assert needle in str(ei.value)
    assert TOKEN not in str(ei.value) and "app.test" not in str(ei.value)


async def test_timeout_va_loi_mang_thanh_loi_tieng_viet(deps: AppDeps) -> None:
    with respx.mock:
        respx.get(f"{BASE}/api/tasks").mock(side_effect=httpx.ReadTimeout("x"))
        respx.get(f"{BASE}/api/plans").mock(side_effect=httpx.ConnectError("khong noi duoc app.test"))
        with pytest.raises(AppApiError, match="không phản hồi"):
            await deps.get_json("/api/tasks")
        with pytest.raises(AppApiError, match="không phản hồi") as ei:
            await deps.get_json("/api/plans")
    assert "app.test" not in str(ei.value)


async def test_json_hong_thanh_loi_tieng_viet(deps: AppDeps) -> None:
    with respx.mock:
        respx.get(f"{BASE}/api/tasks").respond(200, text="<html>không phải json</html>")
        with pytest.raises(AppApiError, match="định dạng"):
            await deps.get_json("/api/tasks")


async def test_loi_cung_duoc_cache_khong_goi_lai(deps: AppDeps) -> None:
    with respx.mock:
        route = respx.get(f"{BASE}/api/finance").respond(403)
        for _ in range(3):
            with pytest.raises(AppApiError):
                await deps.get_json("/api/finance")
    assert route.call_count == 1


def test_today_date() -> None:
    d = AppDeps(
        http=httpx.AsyncClient(), user=UserInfo("u", "n", "admin"), today="2026-10-10", weekday="Thứ Bảy",
    )
    assert d.today_date == date(2026, 10, 10)


# --- review L1, L2, L6 -------------------------------------------------------------------------------------------

async def test_huy_mot_nguoi_cho_khong_lam_hong_nguoi_cho_con_lai(deps: AppDeps) -> None:
    with respx.mock:
        async def slow(_request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.1)
            return httpx.Response(200, json={"tasks": [1]})

        route = respx.get(f"{BASE}/api/tasks").mock(side_effect=slow)
        first = asyncio.create_task(deps.get_json("/api/tasks"))
        second = asyncio.create_task(deps.get_json("/api/tasks"))
        await asyncio.sleep(0.02)
        first.cancel()
        assert await second == {"tasks": [1]}
        assert await deps.get_json("/api/tasks") == {"tasks": [1]}
    assert route.call_count == 1


async def test_task_da_bi_huy_bi_loai_khoi_cache(deps: AppDeps) -> None:
    with respx.mock:
        route = respx.get(f"{BASE}/api/tasks").respond(json={"tasks": []})
        stale = asyncio.ensure_future(asyncio.sleep(10))
        deps.cache["/api/tasks"] = stale
        stale.cancel()
        await asyncio.sleep(0)
        assert await deps.get_json("/api/tasks") == {"tasks": []}
    assert route.call_count == 1


async def test_phan_hoi_qua_lon_bi_tu_choi(deps: AppDeps, monkeypatch: pytest.MonkeyPatch) -> None:
    from family_agent.harness import deps as deps_mod

    monkeypatch.setattr(deps_mod, "MAX_RESPONSE_BYTES", 100)
    with respx.mock:
        respx.get(f"{BASE}/api/tasks").respond(200, text="[" + "1," * 500 + "1]")
        with pytest.raises(AppApiError, match="quá lớn"):
            await deps.get_json("/api/tasks")


async def test_aclose_huy_request_dang_bay_khong_de_lai_canh_bao(deps: AppDeps) -> None:
    with respx.mock:
        async def slow(_request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(5)
            return httpx.Response(200, json={})

        respx.get(f"{BASE}/api/tasks").mock(side_effect=slow)
        waiter = asyncio.create_task(deps.get_json("/api/tasks"))
        await asyncio.sleep(0.02)
        waiter.cancel()
        await deps.aclose()
    assert all(t.done() for t in deps.cache.values())
