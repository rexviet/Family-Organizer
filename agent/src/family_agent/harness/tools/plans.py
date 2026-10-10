"""3 tool ĐỀ XUẤT Lịch (phase 8): chỉ ghi operation vào `deps.outcome`, KHÔNG ghi dữ liệu thật.

Quyền kiểm sớm cho đúng với Node: Khách không tạo/sửa/xoá lịch; sửa/xoá chỉ lịch mình tạo (Admin sửa/xoá mọi lịch).
Lịch không có `updatedAt` → `base` = fingerprint của bản ghi lúc đề xuất (contracts/README.md).

Lịch LẶP: `endDate` của bản ghi là "lặp tới ngày nào" (giờ kết thúc giữ ở phần giờ). Hợp đồng bắt buộc có endDate nên
lịch lặp mới mà người dùng không nói lặp tới khi nào thì mặc định lặp 1 năm (thẻ Duyệt ghi rõ ngày, sửa được trong app).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Final

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from family_agent.contract import fingerprint
from family_agent.harness.deps import AppDeps, ToolError, flag_failures
from family_agent.harness.tools.ask import STOP_MESSAGE
from family_agent.harness.tools.read import fetch_rows
from family_agent.harness.tools.records import (
    DATETIME_FMT,
    MAX_DESCRIPTION,
    MAX_TITLE,
    PENDING,
    clean_text,
    parse_datetime,
    parse_day,
    resolve,
    short,
    stage,
)

_RECURRENCE: Final = ("none", "daily", "weekly", "monthly", "yearly")
DEFAULT_DURATION: Final = timedelta(hours=1)
_FORBIDDEN: Final = "Bạn chỉ sửa/xoá được sự kiện do mình tạo (Admin sửa/xoá được mọi sự kiện)."


def _fmt(d: datetime) -> str:
    return d.strftime(DATETIME_FMT)


def _one_year_later(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29/02
        return d.replace(year=d.year + 1, day=28)


def _js_weekday(d: date) -> int:
    """0 = Chủ nhật … 6 = Thứ Bảy (như app)."""
    return (d.weekday() + 1) % 7


def _weekdays(values: list[int]) -> list[int]:
    out: list[int] = []
    for v in values:
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 6:
            raise ToolError("recurrence_weekdays là các số 0–6 (0 = Chủ nhật, 1 = Thứ Hai … 6 = Thứ Bảy).")
        if v not in out:
            out.append(v)
    if not out:
        raise ToolError("recurrence_weekdays cần ít nhất một thứ.")
    return sorted(out)


def _guard_role(deps: AppDeps) -> None:
    if deps.user.role == "guest":
        raise ToolError("Khách không thêm/sửa/xoá lịch.")


def _label(p: dict[str, Any]) -> str:
    start = str(p.get("startDate") or "")
    return f"{p.get('title', '')} — {short(start)}" if start else str(p.get("title", ""))


def _is_recurring(p: dict[str, Any]) -> bool:
    """Cùng định nghĩa với Node (checkPlanShape): chỉ xét recurrenceType."""
    return str(p.get("recurrenceType") or "none") != "none"


async def _find(deps: AppDeps, ref: str, action: str) -> tuple[dict[str, Any], str] | None:
    """(bản ghi, fingerprint) — kèm kiểm quyền sửa/xoá. Mơ hồ → None (đã hỏi lại)."""
    _guard_role(deps)
    rows = await fetch_rows(deps, "/api/plans", "plans")
    found = resolve(
        deps, ref, rows, kind="sự kiện", action=action, list_tool="list_plans", label=_label,
        prefer=lambda p: _is_recurring(p) or str(p.get("endDate") or p.get("startDate") or "")[:10] >= deps.today,
    )
    if found is None:
        return None
    if found.get("creatorId") != deps.user.id and deps.user.role != "admin":
        raise ToolError(_FORBIDDEN)
    try:
        return found, fingerprint("plan", found)
    except ValueError:
        raise ToolError(f'Sự kiện "{found.get("title", "")}" có dữ liệu lạ nên chưa đề xuất được.') from None


async def propose_create_plan(
    ctx: RunContext[AppDeps],
    title: str,
    start: str,
    end: str | None = None,
    description: str | None = None,
    is_shared: bool | None = None,
    recurrence_type: str | None = None,
    recurrence_weekdays: list[int] | None = None,
    repeat_until: str | None = None,
) -> str:
    """ĐỀ XUẤT thêm một sự kiện vào lịch. KHÔNG ghi thật: người dùng phải bấm Duyệt. Gọi xong lượt kết thúc.

    Cần giờ bắt đầu: người dùng không nói giờ thì hỏi lại bằng ask_user, đừng tự đoán.

    Args:
        title: tên sự kiện.
        start: bắt đầu "YYYY-MM-DD HH:mm".
        end: kết thúc "YYYY-MM-DD HH:mm" (mặc định sau 1 giờ). Với lịch lặp chỉ lấy phần giờ.
        description: mô tả (tuỳ chọn).
        is_shared: True = lịch chung cả nhà (mặc định), False = riêng tư.
        recurrence_type: "daily" | "weekly" | "monthly" | "yearly" để lặp lại; bỏ trống = một lần.
        recurrence_weekdays: với "weekly": các thứ lặp, 0 = Chủ nhật, 1 = Thứ Hai … 6 = Thứ Bảy
            (mặc định = thứ của ngày bắt đầu).
        repeat_until: lặp tới ngày "YYYY-MM-DD" (mặc định 1 năm sau ngày bắt đầu).
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        _guard_role(deps)
        name = clean_text(title, MAX_TITLE, "Tên sự kiện", required=True)
        begin = parse_datetime(start, "start")
        finish = parse_datetime(end, "end") if end is not None else begin + DEFAULT_DURATION
        rtype = recurrence_type or "none"
        if rtype not in _RECURRENCE:
            raise ToolError('recurrence_type phải là "daily", "weekly", "monthly" hoặc "yearly".')
        recurring = rtype != "none"
        if recurrence_weekdays is not None and rtype != "weekly":
            raise ToolError('Chỉ lịch lặp hằng tuần (recurrence_type="weekly") mới chọn recurrence_weekdays.')
        if repeat_until is not None and not recurring:
            raise ToolError("repeat_until chỉ dùng cho lịch lặp lại.")
        if finish < begin and not recurring:
            raise ToolError("Thời gian kết thúc phải sau hoặc bằng thời gian bắt đầu.")

        op: dict[str, Any] = {"type": "plan.create", "title": name, "startDate": _fmt(begin)}
        if recurring:
            until = parse_day(repeat_until, "repeat_until") if repeat_until else _one_year_later(begin.date())
            end_value = datetime.combine(until, finish.time())
            if end_value < begin:
                raise ToolError("repeat_until phải sau hoặc bằng ngày bắt đầu.")
            op["endDate"] = _fmt(end_value)
            op["recurrenceType"] = rtype
            if rtype == "weekly":
                op["recurrenceWeekdays"] = _weekdays(recurrence_weekdays or [_js_weekday(begin.date())])
        else:
            op["endDate"] = _fmt(finish)
        if description:
            op["description"] = clean_text(description, MAX_DESCRIPTION, "Mô tả")
        if is_shared is not None:
            op["isShared"] = bool(is_shared)
        stage(deps, op, target_key="planId", name=name)
        return f'Đã ghi nhận đề xuất thêm sự kiện "{name}". {PENDING}'


async def propose_update_plan(
    ctx: RunContext[AppDeps],
    plan: str,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    is_shared: bool | None = None,
) -> str:
    """ĐỀ XUẤT sửa một sự kiện (đổi tên, dời giờ/ngày, đổi mô tả/chia sẻ). Chỉ nêu trường cần đổi.

    KHÔNG ghi thật: người dùng phải bấm Duyệt. Dời giờ bắt đầu của sự kiện một lần mà không nêu `end` thì giờ kết thúc
    dời theo (giữ nguyên độ dài). Tên khớp nhiều sự kiện thì tool tự hỏi lại. Gọi xong lượt kết thúc.

    Args:
        plan: id sự kiện (từ list_plans) hoặc tên sự kiện.
        title: tên mới.
        start: bắt đầu mới "YYYY-MM-DD HH:mm".
        end: kết thúc mới "YYYY-MM-DD HH:mm" (với lịch lặp: ngày lặp tới + giờ kết thúc).
        description: mô tả mới.
        is_shared: True = lịch chung, False = riêng tư.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        hit = await _find(deps, plan, "sửa")
        if hit is None:
            return STOP_MESSAGE
        found, fp = hit
        name = str(found.get("title", ""))
        wanted: dict[str, Any] = {}
        if title is not None:
            wanted["title"] = clean_text(title, MAX_TITLE, "Tên sự kiện", required=True)
        if description is not None:
            wanted["description"] = clean_text(description, MAX_DESCRIPTION, "Mô tả")
        if is_shared is not None:
            wanted["isShared"] = bool(is_shared)
        if start is not None:
            wanted["startDate"] = _fmt(parse_datetime(start, "start"))
        if end is not None:
            wanted["endDate"] = _fmt(parse_datetime(end, "end"))

        old_start, old_end = str(found.get("startDate") or ""), str(found.get("endDate") or "")
        if start is not None and end is None and not _is_recurring(found):
            try:  # sự kiện một lần: dời cả giờ kết thúc, giữ độ dài
                length = parse_datetime(old_end, "end") - parse_datetime(old_start, "start")
                if length >= timedelta(0):
                    wanted["endDate"] = _fmt(parse_datetime(wanted["startDate"], "start") + length)
            except ToolError:
                pass
        new_start = wanted.get("startDate", old_start)
        new_end = wanted.get("endDate", old_end)
        if not (new_end == "" and _is_recurring(found)) and new_end < new_start:
            raise ToolError("Thời gian kết thúc phải sau hoặc bằng thời gian bắt đầu.")

        changes = {k: v for k, v in wanted.items() if found.get(k) != v}
        if not changes:
            raise ToolError(f'Sự kiện "{name}" đã đúng như vậy — không có thay đổi nào để đề xuất.')
        stage(deps, {"type": "plan.update", "planId": found["id"], "changes": changes, "base": {"fingerprint": fp}},
              target_key="planId", name=name)
        return f'Đã ghi nhận đề xuất sửa sự kiện "{name}". {PENDING}'


async def propose_delete_plan(ctx: RunContext[AppDeps], plan: str) -> str:
    """ĐỀ XUẤT xoá một sự kiện (cả chuỗi nếu là lịch lặp). KHÔNG ghi thật: người dùng phải bấm Duyệt.

    Gọi xong lượt kết thúc.

    Args:
        plan: id sự kiện (từ list_plans) hoặc tên sự kiện; tên khớp nhiều sự kiện thì tool tự hỏi lại.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        hit = await _find(deps, plan, "xoá")
        if hit is None:
            return STOP_MESSAGE
        found, fp = hit
        name = str(found.get("title", ""))
        stage(deps, {"type": "plan.delete", "planId": found["id"], "base": {"fingerprint": fp}},
              target_key="planId", name=name)
        return f'Đã ghi nhận đề xuất xoá sự kiện "{name}". {PENDING}'


plan_toolset: FunctionToolset[AppDeps] = FunctionToolset([
    propose_create_plan, propose_update_plan, propose_delete_plan,
])
