"""Thử tay phase 8: 10 câu Việc/Lịch chạy qua `run_turn` THẬT với model thật (dùng lại khung của phase4_smoke).

KHÔNG nằm trong image và KHÔNG chạy bởi pytest. App Node được giả bằng httpx.MockTransport; mọi request tới "app" được
ghi lại để chứng minh agent không ghi gì (chỉ GET). Hôm nay: Thứ Bảy 2026-10-10, người hỏi Mẹ Lan (member).

    cd agent
    AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x AGENT_LLM_MODEL=kr/deepseek-3.2 \
      uv run python eval/phase8_smoke.py --report ../plans/261010-1652-ai-agent/reports/phase-08-real-model.md
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import phase4_smoke as base  # cùng thư mục eval/
from phase4_smoke import NOW, TurnResult, has


def _plan(i: str, title: str, start: str, end: str, **kw: Any) -> dict[str, Any]:
    row = {"id": i, "title": title, "description": "", "startDate": start, "endDate": end, "isRecurring": False,
           "recurrenceType": "none", "creatorId": "m2", "isShared": True, "color": "sky", "createdAt": NOW}
    row.update(kw)
    return row


base.DATA["/api/plans"] = {"plans": [
    _plan("p1", "Họp lớp", "2026-10-12 19:00", "2026-10-12 21:00"),
    _plan("p2", "Đi bơi", "2026-10-11 08:00", "2026-10-11 09:00"),
    _plan("p3", "Sinh nhật bà", "2026-10-20 18:00", "2026-10-20 21:00"),
    _plan("p4", "Sinh nhật Bin", "2026-11-02 18:00", "2026-11-02 20:00"),
]}


def op(r: TurnResult, kind: str) -> dict[str, Any]:
    found = [o for o in r.operations or [] if o["type"] == kind]
    return found[0] if len(found) == 1 and len(r.operations or []) == 1 else {}


def _create_task(r: TurnResult) -> dict[str, Any]:
    return op(r, "task.create")


base.CASES[:] = [
    ("Giao bé Bin cho mèo ăn lúc 6 giờ tối mai", "propose",
     lambda r: (o := _create_task(r)).get("assigneeId") == "m4" and o.get("dueDate") == "2026-10-11 18:00"),
    ("Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau", "propose",
     lambda r: has((o := _create_task(r)).get("title", ""), "quà") and o.get("dueDate", "")[:10] == "2026-10-16"),
    ("Dời việc sửa vòi nước sang thứ Hai tuần sau", "propose",
     lambda r: (o := op(r, "task.update")).get("taskId") == "t7"
     and o.get("changes", {}).get("dueDate", "")[:10] == "2026-10-12"),
    ("Chuyển việc dọn phòng cho bé Bin", "propose",
     lambda r: (o := op(r, "task.update")).get("taskId") == "t3" and o.get("changes") == {"assigneeId": "m4"}),
    ("Xoá việc họp phụ huynh", "propose", lambda r: op(r, "task.delete").get("taskId") == "t6"),
    ("Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau", "propose",
     lambda r: op(r, "plan.create").get("startDate") == "2026-10-17 09:00"),
    ("Dời buổi họp lớp sang 3 giờ chiều mai", "propose",
     lambda r: (o := op(r, "plan.update")).get("planId") == "p1"
     and o.get("changes", {}).get("startDate") == "2026-10-11 15:00"),
    ("Huỷ lịch đi bơi chủ nhật này", "propose", lambda r: op(r, "plan.delete").get("planId") == "p2"),
    ("Thêm lịch học piano mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau", "propose",
     lambda r: (o := op(r, "plan.create")).get("recurrenceType") == "weekly"
     and o.get("recurrenceWeekdays") == [2, 4] and o.get("startDate", "")[11:] == "17:00"),
    ("Xoá lịch sinh nhật", "ambiguous",
     lambda r: r.kind == "clarification" or (r.kind == "answer" and "?" in r.reply)),
]

if __name__ == "__main__":
    sys.exit(asyncio.run(base.main()))
