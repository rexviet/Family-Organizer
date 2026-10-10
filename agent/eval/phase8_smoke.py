"""Thử tay phase 8: 10 câu Việc/Lịch chạy qua `run_turn` THẬT với model thật (dùng lại khung của phase4_smoke).

KHÔNG nằm trong image và KHÔNG chạy bởi pytest. App Node được giả bằng httpx.MockTransport; mọi request tới "app" được
ghi lại để chứng minh agent không ghi gì (chỉ GET). Hôm nay: Thứ Bảy 2026-10-10, người hỏi Mẹ Lan (member).

    cd agent
    AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x AGENT_LLM_MODEL=kr/deepseek-3.2 \
      uv run python eval/phase8_smoke.py --report ../plans/261010-1652-ai-agent/reports/phase-08-real-model.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
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


def _ops_note(r: Any) -> str:
    """Tóm tắt operation (không chứa gì bí mật: chỉ dữ liệu giả của app giả)."""
    out = []
    for o in r.operations or []:
        body = {k: v for k, v in o.items() if k not in ("type", "base")}
        out.append(f"{o['type']} {json.dumps(body, ensure_ascii=False)}")
    return " ; ".join(out)


def _is_rate_limited(row: Any) -> bool:
    return row.kind == "error" and ("429" in row.note or "rate" in row.note.lower())


async def main() -> int:
    """Như phase4_smoke.main nhưng: nghỉ giữa các câu, lùi + thử lại khi nhà cung cấp trả 429 (model miễn phí),
    ghi chú operation thật, và đếm riêng lỗi do nhà cung cấp (429) với lỗi/sai của model."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", help="ghi bảng markdown vào file này")
    ap.add_argument("--only", type=int, nargs="*", help="chỉ chạy các câu số này (1-10)")
    ap.add_argument("--pause", type=float, default=6.0, help="giây nghỉ giữa các câu")
    ap.add_argument("--retries", type=int, default=5, help="số lần thử lại khi gặp 429")
    args = ap.parse_args()
    need = ["AGENT_LLM_BASE_URL", "AGENT_LLM_API_KEY", "AGENT_LLM_MODEL"]
    if any(not os.environ.get(k) for k in need):
        print("Thiếu env:", ", ".join(need))
        return 2
    settings = base.Settings(AGENT_SHARED_SECRET="s" * 40)  # type: ignore[call-arg]
    model = base.build_model(settings)
    methods: list[str] = []
    gets = [0]
    rows: list[tuple[int, Any, int]] = []
    for n, (q, kind, check) in enumerate(base.CASES, 1):
        if args.only and n not in args.only:
            continue
        attempt = 0
        while True:
            row, r = await base.run_case(model, q, check, methods, gets)
            if not _is_rate_limited(row) or attempt >= args.retries:
                break
            attempt += 1
            wait = min(15 * 2 ** (attempt - 1), 120)
            print(f"   429 nhà cung cấp — câu {n}, thử lại lần {attempt} sau {wait}s")
            await asyncio.sleep(wait)
        row.kind_expected = kind
        if r is not None and r.operations:
            row.note = _ops_note(r)
        elif r is not None:
            row.note = (r.question or r.reply).replace("\n", " ")[:140]
            if r.options:
                row.note += f" options={list(r.options)}"
        rows.append((n, row, attempt))
        print(f"{n:2} {'PASS' if row.ok else 'FAIL'} {kind:9} -> {row.kind:13} req={row.model_requests} "
              f"tools={row.tool_calls} gets={row.app_gets} {row.seconds:5.1f}s retry429={attempt} | {row.note[:160]}")
        await asyncio.sleep(args.pause)
    passed = sum(r.ok for _, r, _ in rows)
    provider = sum(1 for _, r, _ in rows if _is_rate_limited(r))
    writes = [m for m in methods if m != "GET"]
    print(f"TOTAL {passed}/{len(rows)}  model={settings.llm_model}  app_requests={len(methods)} writes={len(writes)} "
          f"provider_429_unresolved={provider}")
    if args.report:
        lines = [
            "| # | Câu hỏi | Kết quả | Kind | Model req | Tool call | GET app | Giây | Thử lại 429 | Ghi chú |",
            "| :-- | :-- | :-- | :-- | --: | --: | --: | --: | --: | :-- |",
        ]
        for n, r, a in rows:
            lines.append(f"| {n} | {r.question} | {'PASS' if r.ok else 'FAIL'} | {r.kind} | {r.model_requests} | "
                         f"{r.tool_calls} | {r.app_gets} | {r.seconds:.1f} | {a} | {r.note.replace('|', '/')[:220]} |")
        lines.append("")
        lines.append(f"**Model `{settings.llm_model}`: {passed}/{len(rows)}** — request tới app: {len(methods)}, "
                     f"method ≠ GET: {len(writes)}; còn 429 của nhà cung cấp sau khi thử lại: {provider}.")
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if not writes else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
