"""Bung sự kiện LẶP thành các ngày cụ thể — bản port của src/utils/recurrence.ts (expandRecurringOccurrences).

Hành vi phải khớp TS từng chữ; case kiểm dùng chung: src/utils/recurrence.cases.json.
Lưu ý khác biệt quy ước: JS `getDay()` 0 = Chủ nhật … 6 = Thứ bảy; Python `weekday()` 0 = Thứ hai
→ luôn đổi qua `_js_weekday`. Ngày chỉ có phần "YYYY-MM-DD" (giờ địa phương), không có múi giờ.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

MAX_ITERATIONS = 400  # `guard < 400` của bản TS: khoảng xem dài hơn bị cắt, giữ nguyên để hai bên cùng kết quả

_DATE_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")


def _js_weekday(d: date) -> int:
    return (d.weekday() + 1) % 7


def parse_plan_date(s: str | None) -> date | None:
    """Phần ngày của "YYYY-MM-DD[ HH:mm]"; None nếu hỏng.

    Giống `new Date(y, m - 1, d)` của JS: tháng/ngày tràn thì cuộn (31/02 → 03/03, ngày 0 → cuối tháng trước),
    năm 0–99 hiểu là 1900–1999.
    """
    m = _DATE_RE.match(str(s or "")[:10])
    if not m:
        return None
    year, month0, day = int(m[1]), int(m[2]) - 1, int(m[3])
    if year <= 99:
        year += 1900
    year += month0 // 12
    month0 %= 12
    try:
        return date(year, month0 + 1, 1) + timedelta(days=day - 1)
    except OverflowError:
        return None
    except ValueError:  # năm ngoài 1..9999
        return None


def expand_recurring_occurrences(plan: Mapping[str, Any], range_start: date, range_end: date) -> list[date]:
    """Các ngày sự kiện lặp diễn ra trong [range_start, range_end] (gồm hai biên).

    - daily: mọi ngày; weekly: đúng các thứ đã chọn (mặc định = thứ của ngày bắt đầu);
      monthly: đúng ngày-trong-tháng của ngày bắt đầu (tháng thiếu ngày thì bỏ); yearly: đúng ngày+tháng.
    - Không có endDate → lặp vô hạn; endDate hỏng hoặc < startDate → sự kiện 1 ngày.
    - Sự kiện không lặp / recurrenceType "none" → [] (người gọi tự xử lý).
    """
    rtype = plan.get("recurrenceType")
    if not plan.get("isRecurring") or not rtype or rtype == "none":
        return []
    start = parse_plan_date(plan.get("startDate"))
    if start is None:
        return []

    frm = max(range_start, start)
    to = range_end
    end_raw = str(plan.get("endDate") or "").strip()
    end_parsed = parse_plan_date(end_raw) if end_raw else None
    if not end_raw:
        last = to
    elif end_parsed is None or end_parsed < start:
        last = start
    else:
        last = end_parsed

    weekdays_raw = plan.get("recurrenceWeekdays")
    # Không phải list (dữ liệu hỏng) → dùng thứ mặc định thay vì ném TypeError.
    weekdays: list[Any] = list(weekdays_raw) if isinstance(weekdays_raw, list) and weekdays_raw else []
    weekdays = weekdays or [_js_weekday(start)]

    result: list[date] = []
    cursor = frm
    guard = 0
    while cursor <= to and cursor <= last and guard < MAX_ITERATIONS:
        if rtype == "daily":
            matches = True
        elif rtype == "weekly":
            matches = _js_weekday(cursor) in weekdays
        elif rtype == "monthly":
            matches = cursor.day == start.day
        elif rtype == "yearly":
            matches = cursor.day == start.day and cursor.month == start.month
        else:
            matches = False
        if matches:
            result.append(cursor)
        cursor += timedelta(days=1)
        guard += 1
    return result
