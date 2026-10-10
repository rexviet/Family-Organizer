"""6 tool đề xuất Việc + Lịch (phase 8): validate, base đúng, update rỗng → từ chối, tên mơ hồ → hỏi lại (≤ 5 lựa chọn),
quyền theo vai trò (khớp endpoint Node), không đụng việc chờ duyệt / trạng thái việc đã xong."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
import respx

from family_agent.contract import fingerprint, validate_operations
from family_agent.harness.deps import AppDeps, Member, ToolError, UserInfo, build_http_client
from family_agent.harness.tools import plans, tasks

pytestmark = pytest.mark.anyio

BASE = "http://app.test:3000"
U0 = "2026-10-01T00:00:00.000Z"
MEMBERS = [
    Member(id="u_lan", fullName="Mẹ Lan", role="member", relation="Mẹ"),
    Member(id="u_admin", fullName="Ba Hùng", role="admin", relation="Ba"),
    Member(id="u_bin", fullName="Bin", role="child", relation="Con"),
    Member(id="u_khach", fullName="Cô Hoa", role="guest", relation="Khách"),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_deps(user: UserInfo) -> AppDeps:
    return AppDeps(
        http=build_http_client(BASE, "tok"), user=user, today="2026-10-10", weekday="Thứ Bảy", members=list(MEMBERS),
    )


@pytest.fixture
async def deps() -> AsyncIterator[AppDeps]:
    d = make_deps(UserInfo("u_lan", "Mẹ Lan", "member"))
    yield d
    await d.http.aclose()


def ctx(d: AppDeps) -> Any:
    return SimpleNamespace(deps=d)


def task(i: str, title: str, **kw: Any) -> dict[str, Any]:
    row = {"id": i, "title": title, "description": "", "status": "todo", "priority": "medium",
           "dueDate": "2026-10-12 17:00", "creatorId": "u_admin", "assigneeId": None, "isShared": True,
           "rewardPoints": 0, "updatedAt": U0}
    row.update(kw)
    return row


def plan(i: str, title: str, **kw: Any) -> dict[str, Any]:
    row = {"id": i, "title": title, "description": "", "startDate": "2026-10-12 08:00", "endDate": "2026-10-12 10:00",
           "isRecurring": False, "recurrenceType": "none", "creatorId": "u_lan", "isShared": True, "color": "rose",
           "createdAt": U0}
    row.update(kw)
    return row


TASKS = [
    task("t1", "Đổ rác"),
    task("t2", "Đổ rác", dueDate="2026-10-05 17:00", status="completed"),
    task("t3", "Rửa bát", assigneeId="u_bin"),
    task("t4", "Rửa xe"),
    task("t5", "Rửa sân"),
    task("t6", "Rửa chén"),
    task("t7", "Rửa rau"),
    task("t8", "Rửa ấm"),
    task("t_pending", "Quét nhà", assigneeId="u_bin", status="in_progress", pendingApproval=True),
    task("t_bin", "Học bài", creatorId="u_bin", assigneeId="u_bin"),
]
PLANS = [
    plan("p1", "Họp phụ huynh"),
    plan("p2", "Sinh nhật bà", creatorId="u_admin", startDate="2026-10-20 18:00", endDate="2026-10-20 21:00"),
    plan("p3", "Sinh nhật Bin", startDate="2026-11-02 18:00", endDate="2026-11-02 20:00"),
    plan("p_week", "Học bơi", isRecurring=True, recurrenceType="weekly", recurrenceWeekdays=[2], endDate=""),
]


def serve() -> None:
    respx.get(f"{BASE}/api/tasks").respond(200, json={"tasks": TASKS})
    respx.get(f"{BASE}/api/plans").respond(200, json={"plans": PLANS})
    respx.get(f"{BASE}/api/users").respond(200, json={"users": []})


def ops(d: AppDeps) -> list[dict[str, Any]]:
    assert validate_operations(d.outcome.operations).ok
    return d.outcome.operations


# --- task.create ------------------------------------------------------------------------------------------------------

async def test_tao_viec_day_du(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await tasks.propose_create_task(
            ctx(deps), title=" Đổ   rác ", due_date="2026-10-15 18:00", assignee_id="u_bin", priority="high",
            reward_points=10,
        )
    assert ops(deps) == [{"type": "task.create", "title": "Đổ rác", "dueDate": "2026-10-15 18:00",
                          "assigneeId": "u_bin", "priority": "high", "rewardPoints": 10}]
    assert "chờ" in msg.lower()


async def test_tao_viec_toi_thieu_chi_co_ten(deps: AppDeps) -> None:
    await tasks.propose_create_task(ctx(deps), title="Mua quà")
    assert ops(deps) == [{"type": "task.create", "title": "Mua quà"}]


@pytest.mark.parametrize("kw", [
    {"title": ""}, {"title": "x" * 201}, {"title": "a", "due_date": "15/10/2026"},
    {"title": "a", "due_date": "2026-02-30"},
    {"title": "a", "due_date": "2026-10-15 25:00"}, {"title": "a", "assignee_id": "u_la"},
    {"title": "a", "priority": "urgent"}, {"title": "a", "reward_points": -1}, {"title": "a", "reward_points": 1001},
])
async def test_tao_viec_sai_dau_vao(deps: AppDeps, kw: dict[str, Any]) -> None:
    with pytest.raises(ToolError):
        await tasks.propose_create_task(ctx(deps), **kw)
    assert deps.outcome.is_empty()


async def test_con_khong_tu_dat_diem_thuong() -> None:
    d = make_deps(UserInfo("u_bin", "Bin", "child"))
    try:
        with pytest.raises(ToolError, match="điểm"):
            await tasks.propose_create_task(ctx(d), title="Tự học", reward_points=5)
        await tasks.propose_create_task(ctx(d), title="Tự học")
        assert ops(d)[0]["title"] == "Tự học"
    finally:
        await d.http.aclose()


# --- task.update ------------------------------------------------------------------------------------------------------

async def test_sua_viec_chi_ghi_truong_thay_doi_va_base_updated_at(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_update_task(ctx(deps), task="t1", due_date="2026-10-14 17:00", priority="medium",
                                        assignee_id="u_bin")
    assert ops(deps) == [{"type": "task.update", "taskId": "t1", "base": {"updatedAt": U0},
                          "changes": {"dueDate": "2026-10-14 17:00", "assigneeId": "u_bin"}}]


async def test_doi_han_chi_ngay_giu_gio_cu(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_update_task(ctx(deps), task="t1", due_date="2026-10-14")
    assert ops(deps)[0]["changes"] == {"dueDate": "2026-10-14 17:00"}


async def test_bo_giao_bang_chuoi_rong(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_update_task(ctx(deps), task="t3", assignee_id="")
    assert ops(deps)[0]["changes"] == {"assigneeId": None}


async def test_sua_khong_co_thay_doi_that_bi_tu_choi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="thay đổi"):
            await tasks.propose_update_task(ctx(deps), task="t1", title="Đổ rác", due_date="2026-10-12 17:00")
        with pytest.raises(ToolError):
            await tasks.propose_update_task(ctx(deps), task="t1")
    assert deps.outcome.is_empty()


async def test_tim_viec_theo_ten_uu_tien_viec_chua_xong(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_update_task(ctx(deps), task="đổ rác", title="Đổ rác & phân loại")
    assert ops(deps)[0]["taskId"] == "t1"  # t2 cùng tên nhưng đã xong


async def test_ten_khop_nhieu_viec_thi_hoi_lai_toi_da_5_lua_chon(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await tasks.propose_delete_task(ctx(deps), task="rửa")
    assert deps.outcome.is_empty()
    asked = deps.clarifications.first()
    assert asked is not None and len(asked.options) == 5
    assert asked.options[0].startswith("Rửa ")
    assert "dừng" in msg.lower()


async def test_tra_loi_bang_dung_lua_chon_thi_chon_duoc(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_delete_task(ctx(deps), task="rửa")
        label = deps.clarifications.first().options[1]  # type: ignore[union-attr]
        deps.clarifications.entries.clear()
        await tasks.propose_delete_task(ctx(deps), task=label)
    assert len(ops(deps)) == 1


async def test_khong_tim_thay_viec_la_loi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="list_tasks"):
            await tasks.propose_update_task(ctx(deps), task="giặt đồ", title="x")


async def test_viec_cho_duyet_va_trang_thai_viec_da_xong_khong_sua_qua_tro_ly(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="chờ duyệt"):
            await tasks.propose_update_task(ctx(deps), task="t_pending", status="todo")
        with pytest.raises(ToolError, match="hoàn thành"):
            await tasks.propose_update_task(ctx(deps), task="t2", status="todo")
        with pytest.raises(ToolError):
            await tasks.propose_update_task(ctx(deps), task="t1", status="completed")


async def test_con_chi_doi_trang_thai_viec_duoc_giao_va_khong_sua_viec_nguoi_khac() -> None:
    d = make_deps(UserInfo("u_bin", "Bin", "child"))
    try:
        with respx.mock:
            serve()
            with pytest.raises(ToolError, match="quyền"):
                await tasks.propose_update_task(ctx(d), task="t1", title="x")
            with pytest.raises(ToolError, match="trạng thái"):
                await tasks.propose_update_task(ctx(d), task="t3", due_date="2026-10-20")
            await tasks.propose_update_task(ctx(d), task="t3", status="in_progress")
            await tasks.propose_update_task(ctx(d), task="t_bin", title="Học bài toán")
        assert [o["taskId"] for o in ops(d)] == ["t3", "t_bin"]
    finally:
        await d.http.aclose()


# --- task.delete ------------------------------------------------------------------------------------------------------

async def test_xoa_viec(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_delete_task(ctx(deps), task="t4")
    assert ops(deps) == [{"type": "task.delete", "taskId": "t4", "base": {"updatedAt": U0}}]


async def test_con_khong_xoa_viec() -> None:
    d = make_deps(UserInfo("u_bin", "Bin", "child"))
    try:
        with respx.mock:
            serve()
            with pytest.raises(ToolError, match="Admin"):
                await tasks.propose_delete_task(ctx(d), task="t_bin")
    finally:
        await d.http.aclose()


async def test_mot_viec_chi_mot_thay_doi_moi_luot(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await tasks.propose_update_task(ctx(deps), task="t4", title="Rửa xe máy")
        with pytest.raises(ToolError, match="Rửa xe"):
            await tasks.propose_delete_task(ctx(deps), task="t4")
    assert len(deps.outcome.operations) == 1


# --- plan.create ------------------------------------------------------------------------------------------------------

async def test_tao_lich_mac_dinh_ket_thuc_sau_1_gio(deps: AppDeps) -> None:
    await plans.propose_create_plan(ctx(deps), title="Họp lớp", start="2026-10-17 19:30")
    assert ops(deps) == [{"type": "plan.create", "title": "Họp lớp", "startDate": "2026-10-17 19:30",
                          "endDate": "2026-10-17 20:30"}]


async def test_tao_lich_qua_nua_dem(deps: AppDeps) -> None:
    await plans.propose_create_plan(ctx(deps), title="Xem pháo hoa", start="2026-12-31 23:30")
    assert ops(deps)[0]["endDate"] == "2027-01-01 00:30"


async def test_tao_lich_lap_hang_tuan_mac_dinh_thu_cua_ngay_bat_dau_va_lap_1_nam(deps: AppDeps) -> None:
    await plans.propose_create_plan(ctx(deps), title="Học bơi", start="2026-10-13 18:00", recurrence_type="weekly")
    assert ops(deps) == [{"type": "plan.create", "title": "Học bơi", "startDate": "2026-10-13 18:00",
                          "endDate": "2027-10-13 19:00", "recurrenceType": "weekly", "recurrenceWeekdays": [2]}]


async def test_tao_lich_lap_co_ngay_ket_thuc_lap(deps: AppDeps) -> None:
    await plans.propose_create_plan(
        ctx(deps), title="Học thêm", start="2026-10-12 17:00", end="2026-10-12 18:30", recurrence_type="weekly",
        recurrence_weekdays=[1, 3], repeat_until="2026-12-31",
    )
    assert ops(deps)[0]["endDate"] == "2026-12-31 18:30"
    assert ops(deps)[0]["recurrenceWeekdays"] == [1, 3]


@pytest.mark.parametrize("kw", [
    {"start": "2026-10-17"},  # thiếu giờ
    {"start": "2026-10-17 19:00", "end": "2026-10-17 18:00"},
    {"start": "2026-02-29 19:00"},
    {"start": "2026-10-17 19:00", "recurrence_weekdays": [1]},  # thứ lặp mà không lặp tuần
    {"start": "2026-10-17 19:00", "recurrence_type": "weekly", "recurrence_weekdays": [7]},
    {"start": "2026-10-17 19:00", "recurrence_type": "hourly"},
    {"start": "2026-10-17 19:00", "repeat_until": "2026-12-31"},  # lặp tới mà không lặp
    {"start": "2026-10-17 19:00", "recurrence_type": "daily", "repeat_until": "2026-10-01"},
])
async def test_tao_lich_sai_dau_vao(deps: AppDeps, kw: dict[str, Any]) -> None:
    with pytest.raises(ToolError):
        await plans.propose_create_plan(ctx(deps), title="x", **kw)
    assert deps.outcome.is_empty()


async def test_khach_khong_tao_lich() -> None:
    d = make_deps(UserInfo("u_khach", "Cô Hoa", "guest"))
    try:
        with pytest.raises(ToolError, match="Khách"):
            await plans.propose_create_plan(ctx(d), title="x", start="2026-10-17 19:00")
    finally:
        await d.http.aclose()


# --- plan.update / delete ---------------------------------------------------------------------------------------------

async def test_doi_gio_bat_dau_lich_mot_lan_doi_ca_ket_thuc_giu_do_dai(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await plans.propose_update_plan(ctx(deps), plan="họp phụ huynh", start="2026-10-13 14:00")
    assert ops(deps) == [{"type": "plan.update", "planId": "p1", "base": {"fingerprint": fingerprint("plan", PLANS[0])},
                          "changes": {"startDate": "2026-10-13 14:00", "endDate": "2026-10-13 16:00"}}]


async def test_doi_gio_lich_lap_vo_han_khong_dung_ngay_ket_thuc(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await plans.propose_update_plan(ctx(deps), plan="p_week", start="2026-10-13 18:30")
    assert ops(deps)[0]["changes"] == {"startDate": "2026-10-13 18:30"}


async def test_sua_lich_khong_doi_gi_bi_tu_choi_va_ket_thuc_truoc_bat_dau_bi_tu_choi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="thay đổi"):
            await plans.propose_update_plan(ctx(deps), plan="p1", title="Họp phụ huynh")
        with pytest.raises(ToolError, match="kết thúc"):
            await plans.propose_update_plan(ctx(deps), plan="p1", end="2026-10-12 07:00")


async def test_sinh_nhat_mo_ho_thi_hoi_lai(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await plans.propose_delete_plan(ctx(deps), plan="sinh nhật")
    asked = deps.clarifications.first()
    assert asked is not None and len(asked.options) == 2
    assert deps.outcome.is_empty()


async def test_thanh_vien_khong_sua_xoa_lich_cua_admin(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="do mình tạo"):
            await plans.propose_delete_plan(ctx(deps), plan="p2")
        with pytest.raises(ToolError, match="do mình tạo"):
            await plans.propose_update_plan(ctx(deps), plan="p2", title="x")
    assert deps.outcome.is_empty()


async def test_admin_xoa_lich_nguoi_khac_base_fingerprint() -> None:
    d = make_deps(UserInfo("u_admin", "Ba Hùng", "admin"))
    try:
        with respx.mock:
            serve()
            await plans.propose_delete_plan(ctx(d), plan="p1")
        base = {"fingerprint": fingerprint("plan", PLANS[0])}
        assert ops(d) == [{"type": "plan.delete", "planId": "p1", "base": base}]
    finally:
        await d.http.aclose()


async def test_hai_viec_cung_ten_cung_han_khac_nguoi_nhan_lua_chon_khong_trung(deps: AppDeps) -> None:
    rows = [task("a1", "Đổ rác", assigneeId="u_bin"), task("a2", "Đổ rác", assigneeId="u_lan"), task("a3", "Đổ rác")]
    with respx.mock:
        respx.get(f"{BASE}/api/tasks").respond(200, json={"tasks": rows})
        await tasks.propose_delete_task(ctx(deps), task="Đổ rác")
        options = deps.clarifications.first().options  # type: ignore[union-attr]
        assert len(set(options)) == 3 and any("Bin" in o for o in options)
        deps.clarifications.entries.clear()
        await tasks.propose_delete_task(ctx(deps), task=options[1])
    assert deps.outcome.operations[0]["taskId"] == "a2"


async def test_nhan_trung_hoan_toan_thi_them_hau_to_id(deps: AppDeps) -> None:
    rows = [task("dup_1111", "Đổ rác"), task("dup_2222", "Đổ rác")]
    with respx.mock:
        respx.get(f"{BASE}/api/tasks").respond(200, json={"tasks": rows})
        await tasks.propose_delete_task(ctx(deps), task="Đổ rác")
        options = deps.clarifications.first().options  # type: ignore[union-attr]
        assert len(set(options)) == 2
        deps.clarifications.entries.clear()
        await tasks.propose_delete_task(ctx(deps), task=options[1])
    assert deps.outcome.operations[0]["taskId"] == "dup_2222"
