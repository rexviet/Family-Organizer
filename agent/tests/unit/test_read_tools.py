"""9 tool đọc: lọc phía client, cắt trường nặng/ảnh, bung lịch lặp, 403 → lỗi tiếng Việt. App được giả bằng respx."""

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
import respx

from family_agent.harness.deps import AppApiError, AppDeps, ToolError, UserInfo, build_http_client
from family_agent.harness.tools import read

pytestmark = pytest.mark.anyio

BASE = "http://app.test:3000"
B64 = "data:image/png;base64," + "A" * 5000


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def deps() -> AsyncIterator[AppDeps]:
    http = build_http_client(BASE, "tok-123")
    yield AppDeps(http=http, user=UserInfo("u_lan", "Mẹ Lan", "member"), today="2026-10-10", weekday="Thứ Bảy")
    await http.aclose()


def ctx(d: AppDeps) -> Any:
    return SimpleNamespace(deps=d)


def serve(path: str, payload: Any, status: int = 200) -> respx.Route:
    return respx.get(f"{BASE}{path}").respond(status, json=payload)


USERS = {"users": [
    {"id": "u_lan", "username": "lan", "fullName": "Mẹ Lan", "role": "member", "familyRelation": "me",
     "avatarColor": "bg-red-500", "avatarImage": B64, "phone": "0900000000", "createdAt": "2026-01-01"},
    {"id": "u_na", "username": "na", "fullName": "Bé Na", "role": "child", "familyRelation": "con",
     "avatarColor": "bg-sky-500", "createdAt": "2026-01-01"},
    {"id": "u_cu", "username": "cu", "fullName": "Người cũ", "role": "guest", "isDeleted": True,
     "avatarColor": "x", "createdAt": "2026-01-01"},
]}


def task(
    i: str, title: str, due: str, assignee: str | None = "u_na", status: str = "todo", **kw: Any
) -> dict[str, Any]:
    return {
        "id": i, "title": title, "description": "mô tả", "status": status, "priority": "medium", "dueDate": due,
        "creatorId": "u_lan", "assigneeId": assignee, "isShared": False, "tags": [], "rewardPoints": 5,
        "comments": [{"id": "c", "content": "dài"}], "history": [{"x": 1}], "proofImage": B64, "proofNote": "xong",
        "createdAt": "2026-10-01T00:00:00.000Z", "updatedAt": "2026-10-02T00:00:00.000Z", **kw,
    }


TASKS = {"tasks": [
    task("t1", "Đánh răng", "2026-10-10 07:00"),
    task("t2", "Làm bài tập toán", "2026-10-10 19:00", status="in_progress"),
    task("t3", "Dọn phòng", "2026-10-11 09:00", status="completed", completedAt="2026-10-11T10:00:00.000Z"),
    task("t5", "Đóng tiền điện", "2026-10-12 12:00", assignee="u_lan"),
    task("t6", "Họp phụ huynh", "2026-10-05 08:00", assignee="u_lan"),
    task("t7", "Việc chưa có hạn", "", assignee=None),
]}


# --- list_members -------------------------------------------------------------

async def test_list_members_gon_va_bo_nguoi_da_xoa(deps: AppDeps) -> None:
    with respx.mock:
        route = serve("/api/users", USERS)
        out = await read.list_members(ctx(deps))
        await read.list_members(ctx(deps))
    assert out == [
        {"id": "u_lan", "fullName": "Mẹ Lan", "role": "member", "relation": "Mẹ"},
        {"id": "u_na", "fullName": "Bé Na", "role": "child", "relation": "Con"},
    ]
    assert route.call_count == 1
    assert "avatar" not in json.dumps(out) and "0900" not in json.dumps(out)


# --- list_tasks ---------------------------------------------------------------

async def test_list_tasks_cat_truong_nang(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/tasks", TASKS)
        out = await read.list_tasks(ctx(deps))
    assert len(out) == 6
    for t in out:
        assert not {"comments", "history", "proofImage", "proofNote", "tags", "createdAt"} & t.keys()
    dump = json.dumps(out)
    assert "base64" not in dump and "dài" not in dump
    t1 = next(t for t in out if t["id"] == "t1")
    assert t1 == {
        "id": "t1", "title": "Đánh răng", "description": "mô tả", "status": "todo", "priority": "medium",
        "dueDate": "2026-10-10 07:00", "assigneeId": "u_na", "creatorId": "u_lan", "isShared": False,
        "rewardPoints": 5, "pendingApproval": False, "overdue": False, "completedAt": None,
    }


async def test_list_tasks_loc_nguoi_nhan_trang_thai_khoang_han(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/tasks", TASKS)
        by_user = await read.list_tasks(ctx(deps), assignee_id="u_lan")
        todo = await read.list_tasks(ctx(deps), status="todo")
        week = await read.list_tasks(ctx(deps), due_from="2026-10-05", due_to="2026-10-11")
        one_day = await read.list_tasks(ctx(deps), due_from="2026-10-10", due_to="2026-10-10")
        open_ = await read.list_tasks(ctx(deps), status="open")
    assert {t["id"] for t in by_user} == {"t5", "t6"}
    assert {t["id"] for t in todo} == {"t1", "t5", "t6", "t7"}
    assert {t["id"] for t in week} == {"t1", "t2", "t3", "t6"}
    assert {t["id"] for t in one_day} == {"t1", "t2"}  # hạn có giờ vẫn khớp theo ngày
    assert "t3" not in {t["id"] for t in open_} and len(open_) == 5


async def test_list_tasks_qua_han_tinh_bang_code(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/tasks", TASKS)
        overdue = await read.list_tasks(ctx(deps), status="overdue")
    assert [t["id"] for t in overdue] == ["t6"]  # t6 hạn 05/10 chưa xong; t3 đã completed; t7 không có hạn
    assert overdue[0]["overdue"] is True


async def test_list_tasks_tim_khong_dau(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/tasks", TASKS)
        out = await read.list_tasks(ctx(deps), query="tien dien")
        out2 = await read.list_tasks(ctx(deps), query="TOÁN")
    assert [t["id"] for t in out] == ["t5"]
    assert [t["id"] for t in out2] == ["t2"]


@pytest.mark.parametrize("kw", [
    {"status": "xong"}, {"due_from": "10/10/2026"}, {"due_to": "2026-13-45"},
    {"due_from": "2026-10-12", "due_to": "2026-10-01"},
])
async def test_list_tasks_tham_so_sai_loi_tieng_viet(deps: AppDeps, kw: dict[str, str]) -> None:
    with respx.mock:
        serve("/api/tasks", TASKS)
        with pytest.raises(ToolError):
            await read.list_tasks(ctx(deps), **kw)


# --- list_plans ---------------------------------------------------------------

PLANS = {"plans": [
    {"id": "p1", "title": "Họp lớp", "description": "", "startDate": "2026-10-12 19:00", "endDate": "2026-10-12 21:00",
     "isRecurring": False, "recurrenceType": "none", "creatorId": "u_lan", "isShared": True, "color": "sky",
     "createdAt": "x"},
    {"id": "p2", "title": "Học bơi", "description": "hồ bơi", "startDate": "2026-09-01 17:00",
     "endDate": "2026-12-31 18:00", "isRecurring": True, "recurrenceType": "weekly", "recurrenceWeekdays": [6, 0],
     "creatorId": "u_lan", "isShared": True, "color": "emerald", "createdAt": "x"},
    {"id": "p3", "title": "Du lịch Đà Lạt", "description": "", "startDate": "2026-10-08 06:00",
     "endDate": "2026-10-13 22:00", "isRecurring": False, "recurrenceType": "none", "creatorId": "u_lan",
     "isShared": True, "color": "rose", "createdAt": "x"},
    {"id": "p4", "title": "Giỗ ông", "description": "", "startDate": "2020-10-14", "endDate": "",
     "isRecurring": True, "recurrenceType": "yearly", "creatorId": "u_lan", "isShared": True, "color": "zinc",
     "createdAt": "x"},
    {"id": "p5", "title": "Xa xôi", "description": "", "startDate": "2027-01-01 09:00", "endDate": "2027-01-01 10:00",
     "isRecurring": False, "recurrenceType": "none", "creatorId": "u_lan", "isShared": True, "color": "x",
     "createdAt": "x"},
]}


async def test_list_plans_bung_lich_lap_trong_khoang(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/plans", PLANS)
        out = await read.list_plans(ctx(deps), date_from="2026-10-10", date_to="2026-10-18")
    rows = [(p["id"], p["date"]) for p in out]
    assert rows == [
        ("p3", "2026-10-08"),  # đang diễn ra (sự kiện nhiều ngày): date = ngày bắt đầu, có thể trước date_from
        ("p2", "2026-10-10"), ("p2", "2026-10-11"), ("p1", "2026-10-12"), ("p4", "2026-10-14"),
        ("p2", "2026-10-17"), ("p2", "2026-10-18"),
    ]
    assert "p5" not in {p["id"] for p in out}
    swim = next(p for p in out if p["id"] == "p2")
    assert swim["time"] == "17:00" and swim["isRecurring"] is True and swim["description"] == "hồ bơi"
    assert not {"color", "createdAt"} & swim.keys()


async def test_list_plans_sap_theo_ngay(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/plans", PLANS)
        out = await read.list_plans(ctx(deps), date_from="2026-10-10", date_to="2026-10-18")
    dates = [p["date"] for p in out]
    assert dates == sorted(dates)


async def test_list_plans_tim_kiem_khong_dau(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/plans", PLANS)
        out = await read.list_plans(ctx(deps), date_from="2026-10-01", date_to="2026-10-31", query="gio ong")
    assert [p["id"] for p in out] == ["p4"]


async def test_list_plans_toi_da_62_ngay(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/plans", PLANS)
        ok = await read.list_plans(ctx(deps), date_from="2026-10-01", date_to="2026-12-01")  # đúng 62 ngày
        assert ok
        with pytest.raises(ToolError, match="62"):
            await read.list_plans(ctx(deps), date_from="2026-10-01", date_to="2026-12-02")
        with pytest.raises(ToolError):
            await read.list_plans(ctx(deps), date_from="2026-10-05", date_to="2026-10-01")
        with pytest.raises(ToolError):
            await read.list_plans(ctx(deps), date_from="hôm nay", date_to="2026-10-01")


# --- thu chi --------------------------------------------------------------------

TXS = {"transactions": [
    {"id": "x1", "type": "expense", "amount": 150000, "category": "food", "account": "cash", "description": "Đi chợ",
     "date": "2026-10-03", "creatorId": "u_lan", "receiptImage": B64, "createdAt": "x"},
    {"id": "x2", "type": "expense", "amount": 1200000, "category": "utilities", "account": "bank",
     "description": "Tiền điện", "date": "2026-10-09", "creatorId": "u_bo", "createdAt": "x"},
    {"id": "x3", "type": "income", "amount": 20000000, "category": "salary", "account": "bank",
     "description": "Lương tháng 10", "date": "2026-10-05", "creatorId": "u_bo", "createdAt": "x"},
    {"id": "x4", "type": "expense", "amount": 90000, "category": "food", "account": "cash", "description": "Ăn sáng",
     "date": "2026-09-30", "creatorId": "u_lan", "createdAt": "x"},
]}


async def test_search_transactions_cat_anh_va_loc(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance", TXS)
        out = await read.search_transactions(ctx(deps), date_from="2026-10-01", date_to="2026-10-31")
        food = await read.search_transactions(
            ctx(deps), date_from="2026-09-01", date_to="2026-10-31", tx_type="expense", category="food",
        )
        mine = await read.search_transactions(
            ctx(deps), date_from="2026-09-01", date_to="2026-10-31", creator_id="u_lan",
        )
        q = await read.search_transactions(ctx(deps), date_from="2026-10-01", date_to="2026-10-31", query="tien dien")
    assert [t["id"] for t in out] == ["x1", "x3", "x2"]  # theo ngày tăng dần
    assert "receiptImage" not in json.dumps(out) and "base64" not in json.dumps(out)
    assert out[0] == {
        "id": "x1", "type": "expense", "amount": 150000, "category": "food", "account": "cash",
        "description": "Đi chợ", "date": "2026-10-03", "creatorId": "u_lan",
    }
    assert {t["id"] for t in food} == {"x1", "x4"}
    assert {t["id"] for t in mine} == {"x1", "x4"}
    assert [t["id"] for t in q] == ["x2"]


async def test_search_transactions_bat_buoc_khoang_ngay_hop_le(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance", TXS)
        with pytest.raises(ToolError):
            await read.search_transactions(ctx(deps), date_from="2026-10-31", date_to="2026-10-01")
        with pytest.raises(ToolError):
            await read.search_transactions(ctx(deps), date_from="2026-10-01", date_to="2026-10-31", tx_type="khac")


async def test_con_hoi_thu_chi_bi_403_thanh_loi_tieng_viet(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance", {"error": "Forbidden"}, status=403)
        with pytest.raises(AppApiError, match="không có quyền"):
            await read.search_transactions(ctx(deps), date_from="2026-10-01", date_to="2026-10-31")


async def test_hang_muc_gom_mac_dinh_va_tu_them(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance/categories", {
            "customCategories": [{"id": "cc_1", "label": "Thú cưng", "emoji": "🐶", "color": "orange",
                                  "createdAt": "x", "updatedAt": "x"}],
            "hiddenBuiltinCategories": ["funeral"],
        })
        out = await read.list_expense_categories(ctx(deps))
    by_id = {c["id"]: c for c in out}
    assert by_id["food"] == {"id": "food", "label": "Ăn uống", "builtin": True, "hidden": False}
    assert by_id["funeral"]["hidden"] is True
    assert by_id["cc_1"] == {"id": "cc_1", "label": "Thú cưng", "builtin": False, "hidden": False}
    assert len(out) == 11 + 1


async def test_ngan_sach_theo_thang(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance/budgets", {"budgets": [
            {"id": "b1", "month": "2026-10", "category": "food", "limit": 3000000, "createdAt": "x", "updatedAt": "x"},
            {"id": "b2", "month": "2026-09", "category": "food", "limit": 2500000, "createdAt": "x", "updatedAt": "x"},
        ]})
        out = await read.list_budgets(ctx(deps), month="2026-10")
        with pytest.raises(ToolError, match="YYYY-MM"):
            await read.list_budgets(ctx(deps), month="10/2026")
    assert out == [{"id": "b1", "month": "2026-10", "category": "food", "limit": 3000000}]


async def test_hoa_don_dinh_ky(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance/recurring-bills", {"recurringBills": [
            {"id": "r1", "title": "Internet", "amount": 220000, "category": "utilities", "account": "bank",
             "frequency": "monthly", "nextDueDate": "2026-10-15", "notes": "FPT", "isActive": True,
             "lastPaidDate": "2026-09-15", "createdAt": "x", "updatedAt": "x"},
        ]})
        out = await read.list_recurring_bills(ctx(deps))
    assert out == [{
        "id": "r1", "title": "Internet", "amount": 220000, "category": "utilities", "frequency": "monthly",
        "nextDueDate": "2026-10-15", "isActive": True, "lastPaidDate": "2026-09-15", "notes": "FPT",
    }]


# --- đi chợ + thực đơn ------------------------------------------------------------

SHOP = {"shoppingItems": [
    {"id": "s1", "name": "Sữa tươi", "quantity": "2 hộp", "isPurchased": False, "creatorId": "u", "cat": "Đạm",
     "createdAt": "x", "updatedAt": "2026-10-01T00:00:00.000Z"},
    {"id": "s2", "name": "Gạo", "quantity": "5 kg", "isPurchased": True, "creatorId": "u",
     "createdAt": "x", "updatedAt": "2026-10-02T00:00:00.000Z"},
]}


async def test_list_shopping_mac_dinh_chi_mon_chua_mua(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/shopping", SHOP)
        todo = await read.list_shopping(ctx(deps))
        everything = await read.list_shopping(ctx(deps), include_purchased=True)
    assert todo == [{"id": "s1", "name": "Sữa tươi", "quantity": "2 hộp", "note": "", "isPurchased": False}]
    assert [i["id"] for i in everything] == ["s1", "s2"]


async def test_meal_plan_none_va_co_du_lieu(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/shopping/meal-plan/current", {"mealPlan": None})
        assert await read.get_meal_plan(ctx(deps)) is None


async def test_meal_plan_gon(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/shopping/meal-plan/current", {"mealPlan": {
            "days": [{"day": 1, "meals": [{"meal": "Trưa", "dishes": ["Cơm", "Canh chua"]}]}],
            "groceries": [
                {"name": "Cá", "cat": "Đạm", "quantity": "500 g", "meals": ["Trưa"], "dishes": ["Canh chua"]},
            ],
            "source": "random", "adults": 2, "children": 1, "updatedAt": "2026-10-09T00:00:00.000Z", "updatedById": "u",
        }})
        out = await read.get_meal_plan(ctx(deps))
    assert out == {
        "days": [{"day": 1, "meals": [{"meal": "Trưa", "dishes": ["Cơm", "Canh chua"]}]}],
        "groceries": [{"name": "Cá", "category": "Đạm", "quantity": "500 g"}],
        "adults": 2, "children": 1, "updatedAt": "2026-10-09T00:00:00.000Z",
    }


# --- review M3, L4 -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [
    ("50000", 50000), (" 1200000 ", 1200000), ("12.5", 12), ("13.5", 14), (150000.0, 150000), (99.6, 100),
    ("abc", 0), ("", 0), (None, 0), (float("nan"), 0), (float("inf"), 0), ("1e400", 0),
])
def test_int_nhan_chuoi_so_va_lam_tron(raw: object, expected: int) -> None:
    assert read._int(raw) == expected


async def test_giao_dich_amount_dang_chuoi_van_dung(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance", {"transactions": [
            {"id": "x1", "type": "expense", "amount": "50000", "category": "food", "account": "cash",
             "description": "Chợ", "date": "2026-10-03", "creatorId": "u"},
        ]})
        out = await read.search_transactions(ctx(deps), date_from="2026-10-01", date_to="2026-10-31")
    assert out[0]["amount"] == 50000


async def test_loc_theo_nhan_hang_muc_tu_them(deps: AppDeps) -> None:
    with respx.mock:
        serve("/api/finance", {"transactions": [
            {"id": "x1", "type": "expense", "amount": 1, "category": "cc_1", "account": "cash", "description": "Cát",
             "date": "2026-10-03", "creatorId": "u"},
            {"id": "x2", "type": "expense", "amount": 2, "category": "food", "account": "cash", "description": "Ăn",
             "date": "2026-10-03", "creatorId": "u"},
        ]})
        serve("/api/finance/categories", {"customCategories": [{"id": "cc_1", "label": "Thú cưng"}],
                                          "hiddenBuiltinCategories": []})
        out = await read.search_transactions(
            ctx(deps), date_from="2026-10-01", date_to="2026-10-31", category="thu cung",
        )
    assert [t["id"] for t in out] == ["x1"]
