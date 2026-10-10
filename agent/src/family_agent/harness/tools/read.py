"""9 tool ĐỌC (spec §6.1). Docstring + kiểu trả về là giao diện model nhìn thấy → tiếng Việt, ghi rõ đơn vị.

Mỗi tool chỉ gọi route DANH SÁCH (không ghép id vào URL) rồi lọc phía agent; mỗi endpoint tối đa 1 request/lượt.
Chỉ trả trường cần thiết: không ảnh/base64, không `history`/`comments`.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Final, TypedDict

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from family_agent.harness.deps import AppApiError, AppDeps, Member, ToolError
from family_agent.harness.recurrence import expand_recurring_occurrences, parse_plan_date
from family_agent.harness.vocab import BUILTIN_CATEGORIES, RELATION_LABELS, fold

MAX_PLAN_RANGE_DAYS: Final = 62
MAX_DESCRIPTION: Final = 500

_DAY_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_MONTH_RE = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
_TASK_STATUSES: Final = ("todo", "in_progress", "completed", "overdue", "open")
_TX_TYPES: Final = ("income", "expense")


class Task(TypedDict):
    id: str
    title: str
    description: str
    status: str  # todo | in_progress | completed | overdue
    priority: str  # low | medium | high
    dueDate: str  # "YYYY-MM-DD HH:mm" ("" nếu không có hạn)
    assigneeId: str | None  # None = chưa giao / việc chung
    creatorId: str
    isShared: bool
    rewardPoints: int
    pendingApproval: bool  # trẻ đã báo xong, chờ người lớn duyệt
    overdue: bool  # đã quá hạn (tính theo hôm nay) mà chưa hoàn thành
    completedAt: str | None


class PlanOccurrence(TypedDict):
    id: str
    title: str
    description: str
    date: str  # ngày diễn ra "YYYY-MM-DD"
    time: str | None  # giờ bắt đầu "HH:mm", None nếu cả ngày
    startDate: str  # "YYYY-MM-DD HH:mm" — của cả sự kiện/chuỗi lặp
    endDate: str
    isRecurring: bool
    recurrenceType: str  # none | daily | weekly | monthly | yearly
    isShared: bool
    creatorId: str


class Transaction(TypedDict):
    id: str
    type: str  # income | expense
    amount: int  # đồng VND, số nguyên
    category: str  # id hạng mục (xem list_expense_categories)
    account: str  # cash | bank | e_wallet
    description: str
    date: str  # YYYY-MM-DD
    creatorId: str


class Category(TypedDict):
    id: str
    label: str
    builtin: bool
    hidden: bool


class Budget(TypedDict):
    id: str
    month: str  # YYYY-MM
    category: str
    limit: int  # đồng VND


class Bill(TypedDict):
    id: str
    title: str
    amount: int  # đồng VND
    category: str
    frequency: str  # weekly | monthly | yearly
    nextDueDate: str  # YYYY-MM-DD
    isActive: bool
    lastPaidDate: str | None
    notes: str


class ShoppingItem(TypedDict):
    id: str
    name: str
    quantity: str
    note: str
    isPurchased: bool


class MealRow(TypedDict):
    meal: str
    dishes: list[str]


class MealDay(TypedDict):
    day: int
    meals: list[MealRow]


class Grocery(TypedDict):
    name: str
    category: str
    quantity: str


class MealPlan(TypedDict):
    days: list[MealDay]
    groceries: list[Grocery]
    adults: int
    children: int
    updatedAt: str


# --- tiện ích nội bộ ----------------------------------------------------------------


def _day(value: str, name: str) -> date:
    if not isinstance(value, str) or not _DAY_RE.match(value):
        raise ToolError(f"{name} phải có dạng YYYY-MM-DD (ví dụ 2026-10-10).")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"{name} không phải ngày có thật: {value}.") from None


def _range(date_from: str, date_to: str, *, a: str = "date_from", b: str = "date_to") -> tuple[date, date]:
    start, end = _day(date_from, a), _day(date_to, b)
    if start > end:
        raise ToolError(f"{a} phải trước hoặc bằng {b}.")
    return start, end


def _int(v: Any) -> int:
    """Số nguyên VND. Node có thể lưu số dạng chuỗi ("50000") hoặc số thực; số thực làm tròn (round, .5 chẵn);
    không đọc được / vô cực / NaN → 0."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            v = float(v.strip())
        except ValueError:
            return 0
    if isinstance(v, float) and math.isfinite(v):
        return round(v)
    return 0


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


async def fetch_rows(deps: AppDeps, path: str, key: str) -> list[dict[str, Any]]:
    data = await deps.get_json(path)
    items = data.get(key) if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise AppApiError("Dữ liệu từ ứng dụng không đúng định dạng.")
    return [i for i in items if isinstance(i, dict)]


def _matches(query: str | None, *texts: str) -> bool:
    if not query or not query.strip():
        return True
    needle = fold(query)
    return any(needle in fold(t) for t in texts)


# --- tool ------------------------------------------------------------------------------


async def load_members(deps: AppDeps) -> list[Member]:
    users = await fetch_rows(deps, "/api/users", "users")
    return [
        Member(
            id=_s(u.get("id")), fullName=_s(u.get("fullName")), role=_s(u.get("role")),
            relation=RELATION_LABELS.get(_s(u.get("familyRelation")), ""),
        )
        for u in users
        if not u.get("isDeleted") and _s(u.get("id"))
    ]


async def list_members(ctx: RunContext[AppDeps]) -> list[Member]:
    """Danh sách thành viên gia đình: id, họ tên, vai trò (admin|member|child|guest) và quan hệ (Mẹ, Con…).

    Dùng id ở đây để lọc việc/khoản chi theo người (assignee_id, creator_id).
    """
    return await load_members(ctx.deps)


def _task_row(t: dict[str, Any], today: str) -> Task:
    status = _s(t.get("status"))
    due = _s(t.get("dueDate"))
    assignee = t.get("assigneeId")
    return Task(
        id=_s(t.get("id")), title=_s(t.get("title")), description=_s(t.get("description"))[:MAX_DESCRIPTION],
        status=status, priority=_s(t.get("priority")), dueDate=due,
        assigneeId=assignee if isinstance(assignee, str) and assignee else None,
        creatorId=_s(t.get("creatorId")), isShared=bool(t.get("isShared")), rewardPoints=_int(t.get("rewardPoints")),
        pendingApproval=bool(t.get("pendingApproval")),
        overdue=status == "overdue" or (status != "completed" and bool(due) and due[:10] < today),
        completedAt=t.get("completedAt") if isinstance(t.get("completedAt"), str) else None,
    )


async def list_tasks(
    ctx: RunContext[AppDeps],
    status: str | None = None,
    assignee_id: str | None = None,
    due_from: str | None = None,
    due_to: str | None = None,
    query: str | None = None,
) -> list[Task]:
    """Danh sách việc (đã lọc theo quyền của người hỏi), sắp theo hạn tăng dần. Mọi tham số đều tuỳ chọn.

    Args:
        status: "todo" | "in_progress" | "completed" | "overdue" (quá hạn chưa xong) | "open" (mọi việc chưa xong).
        assignee_id: id người được giao (lấy từ list_members).
        due_from: hạn từ ngày này trở đi, YYYY-MM-DD (gồm biên). Việc không có hạn bị loại khi có due_from/due_to.
        due_to: hạn đến hết ngày này, YYYY-MM-DD (gồm biên).
        query: từ khoá trong tiêu đề/mô tả, không phân biệt hoa thường và dấu.
    """
    deps = ctx.deps
    if status is not None and status not in _TASK_STATUSES:
        raise ToolError(f"status phải là một trong: {', '.join(_TASK_STATUSES)}.")
    start = _day(due_from, "due_from") if due_from else None
    end = _day(due_to, "due_to") if due_to else None
    if start and end and start > end:
        raise ToolError("due_from phải trước hoặc bằng due_to.")

    out: list[Task] = []
    for raw in await fetch_rows(deps, "/api/tasks", "tasks"):
        t = _task_row(raw, deps.today)
        if status == "open":
            if t["status"] == "completed":
                continue
        elif status == "overdue":
            if not t["overdue"]:
                continue
        elif status is not None and t["status"] != status:
            continue
        if assignee_id is not None and t["assigneeId"] != assignee_id:
            continue
        if start or end:
            due = t["dueDate"][:10]
            if not due or (start and due < start.isoformat()) or (end and due > end.isoformat()):
                continue
        if not _matches(query, t["title"], t["description"]):
            continue
        out.append(t)
    out.sort(key=lambda t: (t["dueDate"] or "9999", t["title"]))
    return out


def _plan_row(p: dict[str, Any], day: date) -> PlanOccurrence:
    start = _s(p.get("startDate"))
    time = start[11:16] if re.fullmatch(r"[0-9]{2}:[0-9]{2}", start[11:16]) else None
    return PlanOccurrence(
        id=_s(p.get("id")), title=_s(p.get("title")), description=_s(p.get("description"))[:MAX_DESCRIPTION],
        date=day.isoformat(), time=time, startDate=start, endDate=_s(p.get("endDate")),
        isRecurring=bool(p.get("isRecurring")), recurrenceType=_s(p.get("recurrenceType")) or "none",
        isShared=bool(p.get("isShared")), creatorId=_s(p.get("creatorId")),
    )


async def list_plans(
    ctx: RunContext[AppDeps], date_from: str, date_to: str, query: str | None = None
) -> list[PlanOccurrence]:
    """Lịch/sự kiện trong khoảng [date_from, date_to] (gồm biên, tối đa 62 ngày), sắp theo ngày. Đã bung sự kiện lặp.

    Mỗi dòng là MỘT lần diễn ra. Sự kiện lặp cho một dòng mỗi lần xuất hiện trong khoảng. Sự kiện không lặp kéo
    dài nhiều ngày chỉ có MỘT dòng với `date` = ngày bắt đầu (có thể trước date_from nếu đang diễn ra); xem
    startDate/endDate để biết cả khoảng.

    Args:
        date_from: YYYY-MM-DD.
        date_to: YYYY-MM-DD.
        query: từ khoá trong tiêu đề/mô tả, không phân biệt hoa thường và dấu.
    """
    start, end = _range(date_from, date_to)
    if (end - start).days + 1 > MAX_PLAN_RANGE_DAYS:
        raise ToolError(f"Khoảng ngày tối đa {MAX_PLAN_RANGE_DAYS} ngày. Hãy chia nhỏ khoảng cần xem.")

    out: list[PlanOccurrence] = []
    for p in await fetch_rows(ctx.deps, "/api/plans", "plans"):
        if not _matches(query, _s(p.get("title")), _s(p.get("description"))):
            continue
        rtype = _s(p.get("recurrenceType"))
        if p.get("isRecurring") and rtype not in ("", "none"):
            out.extend(_plan_row(p, d) for d in expand_recurring_occurrences(p, start, end))
            continue
        first = parse_plan_date(_s(p.get("startDate")))
        if first is None:
            continue
        last = parse_plan_date(_s(p.get("endDate"))) or first
        if first <= end and max(last, first) >= start:
            out.append(_plan_row(p, first))
    out.sort(key=lambda r: (r["date"], r["time"] or "", r["title"]))
    return out


async def search_transactions(
    ctx: RunContext[AppDeps],
    date_from: str,
    date_to: str,
    tx_type: str | None = None,
    category: str | None = None,
    creator_id: str | None = None,
    query: str | None = None,
) -> list[Transaction]:
    """Giao dịch thu chi trong khoảng [date_from, date_to] (gồm biên), ngày tăng dần. Chỉ admin/member xem được.

    Số tiền là số nguyên đồng VND. Muốn tổng/thống kê hãy cộng trong code, đừng ước lượng.

    Args:
        date_from: YYYY-MM-DD.
        date_to: YYYY-MM-DD.
        tx_type: "income" (thu) hoặc "expense" (chi).
        category: id hạng mục (food, utilities…; hạng mục tự thêm xem list_expense_categories). Nhãn mặc định
            như "Ăn uống" cũng được nhận.
        creator_id: id người ghi khoản này (lấy từ list_members).
        query: từ khoá trong mô tả, không phân biệt hoa thường và dấu.
    """
    start, end = _range(date_from, date_to)
    if tx_type is not None and tx_type not in _TX_TYPES:
        raise ToolError('tx_type phải là "income" hoặc "expense".')
    wanted_cat = None
    if category:
        wanted_cat = next((cid for cid, label in BUILTIN_CATEGORIES.items() if fold(label) == fold(category)), None)
        is_id = category.casefold() in BUILTIN_CATEGORIES or category.casefold().startswith("cc_")
        if wanted_cat is None and not is_id:  # nhãn hạng mục gia đình tự thêm ("Thú cưng") → id cc_…
            custom = (await ctx.deps.get_json("/api/finance/categories")) or {}
            custom_list = custom.get("customCategories") if isinstance(custom, dict) else None
            wanted_cat = next(
                (_s(c.get("id")).casefold() for c in custom_list or []
                 if isinstance(c, dict) and fold(_s(c.get("label"))) == fold(category)),
                None,
            )
        wanted_cat = wanted_cat or category.casefold()

    out: list[Transaction] = []
    for t in await fetch_rows(ctx.deps, "/api/finance", "transactions"):
        day = _s(t.get("date"))[:10]
        if not (start.isoformat() <= day <= end.isoformat()):
            continue
        if tx_type is not None and t.get("type") != tx_type:
            continue
        if wanted_cat is not None and _s(t.get("category")).casefold() != wanted_cat:
            continue
        if creator_id is not None and t.get("creatorId") != creator_id:
            continue
        if not _matches(query, _s(t.get("description"))):
            continue
        out.append(Transaction(
            id=_s(t.get("id")), type=_s(t.get("type")), amount=_int(t.get("amount")), category=_s(t.get("category")),
            account=_s(t.get("account")), description=_s(t.get("description")), date=day,
            creatorId=_s(t.get("creatorId")),
        ))
    out.sort(key=lambda t: t["date"])
    return out


async def list_expense_categories(ctx: RunContext[AppDeps]) -> list[Category]:
    """Hạng mục chi: mặc định (food, utilities…) và hạng mục gia đình tự thêm (id dạng cc_…). Chỉ admin/member xem được.

    `hidden` = hạng mục mặc định đã bị ẩn khỏi ô chọn (giao dịch cũ vẫn có thể dùng).
    """
    data = await ctx.deps.get_json("/api/finance/categories")
    if not isinstance(data, dict):
        raise AppApiError("Dữ liệu từ ứng dụng không đúng định dạng.")
    hidden = {h for h in data.get("hiddenBuiltinCategories") or [] if isinstance(h, str)}
    out = [
        Category(id=cid, label=label, builtin=True, hidden=cid in hidden)
        for cid, label in BUILTIN_CATEGORIES.items()
    ]
    for c in data.get("customCategories") or []:
        if isinstance(c, dict) and _s(c.get("id")):
            out.append(Category(id=_s(c.get("id")), label=_s(c.get("label")), builtin=False, hidden=False))
    return out


async def list_budgets(ctx: RunContext[AppDeps], month: str) -> list[Budget]:
    """Hạn mức chi theo hạng mục của một tháng. Chỉ admin/member xem được.

    Args:
        month: tháng cần xem, YYYY-MM (ví dụ 2026-10).
    """
    if not isinstance(month, str) or not _MONTH_RE.match(month):
        raise ToolError("month phải có dạng YYYY-MM (ví dụ 2026-10).")
    return [
        Budget(id=_s(b.get("id")), month=month, category=_s(b.get("category")), limit=_int(b.get("limit")))
        for b in await fetch_rows(ctx.deps, "/api/finance/budgets", "budgets")
        if b.get("month") == month
    ]


async def list_recurring_bills(ctx: RunContext[AppDeps]) -> list[Bill]:
    """Hoá đơn/khoản chi định kỳ (tiền điện, internet…) với kỳ hạn kế tiếp. Chỉ admin/member xem được."""
    return [
        Bill(
            id=_s(b.get("id")), title=_s(b.get("title")), amount=_int(b.get("amount")), category=_s(b.get("category")),
            frequency=_s(b.get("frequency")), nextDueDate=_s(b.get("nextDueDate")), isActive=bool(b.get("isActive")),
            lastPaidDate=b.get("lastPaidDate") if isinstance(b.get("lastPaidDate"), str) else None,
            notes=_s(b.get("notes")),
        )
        for b in await fetch_rows(ctx.deps, "/api/finance/recurring-bills", "recurringBills")
    ]


def shopping_row(i: dict[str, Any]) -> ShoppingItem:
    return ShoppingItem(
        id=_s(i.get("id")), name=_s(i.get("name")), quantity=_s(i.get("quantity")), note=_s(i.get("note")),
        isPurchased=bool(i.get("isPurchased")),
    )


async def list_shopping(ctx: RunContext[AppDeps], include_purchased: bool = False) -> list[ShoppingItem]:
    """Danh sách đi chợ. Mặc định chỉ món CHƯA mua; đặt include_purchased=True để lấy cả món đã mua.

    id ở đây dùng cho propose_set_purchased / propose_remove_shopping_items.
    """
    return [
        shopping_row(i)
        for i in await fetch_rows(ctx.deps, "/api/shopping", "shoppingItems")
        if include_purchased or not i.get("isPurchased")
    ]


async def get_meal_plan(ctx: RunContext[AppDeps]) -> MealPlan | None:
    """Thực đơn tuần đang dùng chung (món theo ngày/bữa + danh sách nguyên liệu cần mua). None nếu chưa lập."""
    data = await ctx.deps.get_json("/api/shopping/meal-plan/current")
    plan = data.get("mealPlan") if isinstance(data, dict) else None
    if not isinstance(plan, dict):
        return None
    days = [
        MealDay(
            day=_int(d.get("day")),
            meals=[
                MealRow(meal=_s(m.get("meal")), dishes=[x for x in m.get("dishes") or [] if isinstance(x, str)])
                for m in d.get("meals") or [] if isinstance(m, dict)
            ],
        )
        for d in plan.get("days") or [] if isinstance(d, dict)
    ]
    groceries = [
        Grocery(name=_s(g.get("name")), category=_s(g.get("cat")), quantity=_s(g.get("quantity")))
        for g in plan.get("groceries") or [] if isinstance(g, dict)
    ]
    return MealPlan(
        days=days, groceries=groceries, adults=_int(plan.get("adults")), children=_int(plan.get("children")),
        updatedAt=_s(plan.get("updatedAt")),
    )


read_toolset: FunctionToolset[AppDeps] = FunctionToolset([
    list_members, list_tasks, list_plans, search_transactions, list_expense_categories,
    list_budgets, list_recurring_bills, list_shopping, get_meal_plan,
])
