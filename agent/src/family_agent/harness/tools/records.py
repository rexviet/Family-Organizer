"""Phần dùng chung của tool đề xuất Việc/Lịch: kiểm chuỗi/ngày, tìm bản ghi theo id hoặc tên, ghi đề xuất.

Tìm bản ghi: id khớp đúng → lấy luôn; không thì so tên không dấu (khớp đúng tên trước, rồi chứa từ khoá), ưu tiên bản
ghi "còn hiệu lực" (vd. việc chưa xong). Còn nhiều hơn một → hỏi lại người dùng với tối đa 5 lựa chọn (spec §6.3).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Final

from family_agent.harness.deps import AppDeps, ToolError
from family_agent.harness.outcome import OutcomeError
from family_agent.harness.tools.read import load_members
from family_agent.harness.vocab import fold

MAX_TITLE: Final = 200
MAX_DESCRIPTION: Final = 2000
MAX_CHOICES: Final = 5
PENDING: Final = "Đây mới là ĐỀ XUẤT, đang chờ người dùng duyệt — chưa có gì được thay đổi thật."

_DATE_RE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_DATETIME_RE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$")
DATETIME_FMT: Final = "%Y-%m-%d %H:%M"


def clean_text(value: object, limit: int, what: str, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ToolError(f"{what} phải là chuỗi.")
    out = " ".join(value.split())
    if required and not out:
        raise ToolError(f"{what} không được để trống.")
    if len(out) > limit:
        raise ToolError(f"{what} tối đa {limit} ký tự.")
    return out


def parse_day(value: str, what: str) -> date:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ToolError(f"{what} phải có dạng YYYY-MM-DD (ví dụ 2026-10-15).")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"{what} không phải ngày có thật: {value}.") from None


def parse_datetime(value: str, what: str) -> datetime:
    if not isinstance(value, str) or not _DATETIME_RE.match(value):
        raise ToolError(f"{what} phải có dạng YYYY-MM-DD HH:mm (ví dụ 2026-10-15 18:30).")
    try:
        return datetime.strptime(value, DATETIME_FMT)
    except ValueError:
        raise ToolError(f"{what} không phải thời điểm có thật: {value}.") from None


def is_date_only(value: str) -> bool:
    return bool(_DATE_RE.match(value))


def short(value: str) -> str:
    """"YYYY-MM-DD HH:mm" → "HH:mm dd/MM"; "YYYY-MM-DD" → "dd/MM" (khớp shortDate của preview Node)."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}:\d{2}))?", value or "")
    if not m:
        return value or "(trống)"
    day = f"{m[3]}/{m[2]}"
    return f"{m[4]} {day}" if m[4] else day


def resolve(
    deps: AppDeps,
    ref: str,
    rows: list[dict[str, Any]],
    *,
    kind: str,
    action: str,
    list_tool: str,
    label: Callable[[dict[str, Any]], str],
    prefer: Callable[[dict[str, Any]], bool] = lambda _r: True,
) -> dict[str, Any] | None:
    """Bản ghi theo id/tên/nhãn lựa chọn. Mơ hồ → ghi câu hỏi lại và trả None; không thấy → ToolError."""
    key = ref.strip() if isinstance(ref, str) else ""
    if not key:
        raise ToolError(f"Cần id hoặc tên {kind} (lấy từ {list_tool}).")
    for r in rows:
        if r.get("id") == key:
            return r
    labels = unique_labels(rows, label)
    # Người dùng trả lời bằng đúng một lựa chọn đã hỏi ở lượt trước (nhãn là duy nhất).
    by_label = [r for r in rows if labels[id(r)] == key]
    if len(by_label) == 1:
        return by_label[0]
    needle = fold(key)
    matches = [r for r in rows if needle and needle in fold(str(r.get("title", "")))]
    pool = [r for r in matches if fold(str(r.get("title", ""))) == needle] or matches
    if len(pool) > 1:
        live = [r for r in pool if prefer(r)]
        pool = live or pool
    if len(pool) == 1:
        return pool[0]
    if not pool:
        raise ToolError(f'Không tìm thấy {kind} nào khớp "{key}". Hãy dùng {list_tool} để lấy đúng id.')
    deps.clarifications.ask(
        f'Có {len(pool)} {kind} khớp "{key}" — bạn muốn {action} {kind} nào?',
        [labels[id(r)] for r in pool[:MAX_CHOICES]],
    )
    return None


def unique_labels(rows: list[dict[str, Any]], label: Callable[[dict[str, Any]], str]) -> dict[int, str]:
    """Nhãn lựa chọn cho từng bản ghi (khoá = id(object)); nhãn trùng thì thêm "#" + 4 ký tự cuối của id bản ghi
    để người dùng bấm lựa chọn nào cũng chỉ về đúng MỘT bản ghi (không hỏi lại vòng lặp)."""
    base = {id(r): label(r) for r in rows}
    counts: dict[str, int] = {}
    for text in base.values():
        counts[text] = counts.get(text, 0) + 1
    out: dict[int, str] = {}
    for r in rows:
        text = base[id(r)]
        out[id(r)] = f"{text} #{str(r.get('id', ''))[-4:]}" if counts[text] > 1 else text
    return out


def stage(deps: AppDeps, op: dict[str, Any], *, target_key: str, name: str) -> None:
    """Ghi MỘT operation. Mỗi bản ghi chỉ một thay đổi trong lượt (đề xuất y hệt cái cũ thì bỏ qua)."""
    target = op.get(target_key)
    if target is not None:
        for prev in deps.outcome.operations:
            if prev.get(target_key) == target and prev != op:
                raise ToolError(f'"{name}" đã có một đề xuất khác trong lượt này; mỗi mục chỉ đề xuất một thay đổi.')
    try:
        deps.outcome.add(op)
    except OutcomeError as e:
        raise ToolError(str(e)) from None


async def member_ids(deps: AppDeps) -> set[str]:
    """id thành viên (lấy lúc đầu lượt; lỗi thì thử đọc lại một lần qua cache của lượt)."""
    if deps.members:
        return {m["id"] for m in deps.members}
    deps.members = await load_members(deps)
    return {m["id"] for m in deps.members}
