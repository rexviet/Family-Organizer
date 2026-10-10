"""Thử tay phase 4: 10 câu của spike phase 1 chạy qua `run_turn` THẬT với model thật.

KHÔNG nằm trong image (Dockerfile chỉ COPY src) và KHÔNG chạy bởi pytest (testpaths = tests).
Phía app Node được giả bằng httpx.MockTransport (dữ liệu giống spike, đúng dạng JSON của API thật);
mọi request tới "app" được ghi lại để chứng minh agent không ghi gì (chỉ GET).

    cd agent
    AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x AGENT_LLM_MODEL=kr/deepseek-3.2 \
      uv run python eval/phase4_smoke.py --report ../plans/261010-1652-ai-agent/reports/phase-04-real-model.md

Dữ liệu "tuần này": hôm nay là Thứ Bảy 2026-10-10 → tuần này = 10-05…10-11. Khác spike, hạn "Đóng tiền điện" của mẹ Lan
đặt vào Chủ nhật 10-11 (spike đặt 10-12 vì khi đó "tuần này" chưa được định nghĩa là Thứ Hai–Chủ nhật).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from family_agent.harness.agent import TurnInput, TurnLimits, TurnResult, run_turn
from family_agent.harness.deps import UserInfo
from family_agent.harness.vocab import fold
from family_agent.model import build_model
from family_agent.settings import Settings

APP = "http://app.local:3000"
TOKEN = "smoke-token-khong-duoc-lo"  # noqa: S105 — token giả cho app giả
NOW = "2026-10-01T00:00:00.000Z"


def _user(i: str, name: str, role: str, rel: str) -> dict[str, Any]:
    return {"id": i, "username": i, "fullName": name, "role": role, "familyRelation": rel,
            "avatarColor": "bg-sky-500", "createdAt": NOW}


def _task(i: str, title: str, who: str, due: str, status: str = "todo") -> dict[str, Any]:
    return {"id": i, "title": title, "description": "", "status": status, "priority": "medium", "dueDate": due,
            "creatorId": "m2", "assigneeId": who, "isShared": False, "tags": [], "rewardPoints": 0,
            "comments": [{"id": "c1", "userId": "m2", "username": "lan", "content": "nhắc nhé", "createdAt": NOW}],
            "history": [{"id": "h1", "action": "created"}], "proofImage": "data:image/png;base64," + "A" * 3000,
            "proofNote": None, "createdAt": NOW, "updatedAt": NOW}


def _shop(i: str, name: str, qty: str, bought: bool) -> dict[str, Any]:
    return {"id": i, "name": name, "quantity": qty, "isPurchased": bought, "creatorId": "m2",
            "createdAt": NOW, "updatedAt": NOW}


DATA: dict[str, Any] = {
    "/api/users": {"users": [
        _user("m1", "Bố Minh", "admin", "ba"), _user("m2", "Mẹ Lan", "member", "me"),
        _user("m3", "Bé Na", "child", "con"), _user("m4", "Bé Bin", "child", "con"),
    ]},
    "/api/tasks": {"tasks": [
        _task("t1", "Đánh răng", "m3", "2026-10-10 07:00"),
        _task("t2", "Làm bài tập toán", "m3", "2026-10-10 19:00"),
        _task("t3", "Dọn phòng", "m3", "2026-10-11 09:00"),
        _task("t4", "Cho mèo ăn", "m4", "2026-10-10 18:00", "completed"),
        _task("t5", "Đóng tiền điện", "m2", "2026-10-11 12:00"),
        _task("t6", "Họp phụ huynh", "m2", "2026-10-14 08:00"),
        _task("t7", "Sửa vòi nước", "m1", "2026-10-20 09:00"),
    ]},
    "/api/shopping": {"shoppingItems": [
        _shop("s1", "Sữa tươi", "2 hộp", False), _shop("s2", "Gạo", "5 kg", True),
        _shop("s3", "Dầu ăn", "1 chai", False),
    ]},
    "/api/plans": {"plans": []},
    "/api/finance": {"transactions": []},
    "/api/finance/categories": {"customCategories": [], "hiddenBuiltinCategories": []},
    "/api/finance/budgets": {"budgets": []},
    "/api/finance/recurring-bills": {"recurringBills": []},
    "/api/shopping/meal-plan/current": {"mealPlan": None},
}


def has(text: str, *words: str) -> bool:
    t = fold(text)
    return all(fold(w) in t for w in words)


def added(r: TurnResult) -> str:
    return " ".join(i["name"] for op in r.operations or [] if op["type"] == "shopping.add" for i in op["items"])


Check = Callable[[TurnResult], bool]
CASES: list[tuple[str, str, Check]] = [
    ("Hôm nay bé Na có những việc gì?", "read", lambda r: r.kind == "answer" and has(r.reply, "đánh răng", "toán")),
    ("Ai đang có nhiều việc chưa xong nhất?", "read", lambda r: r.kind == "answer" and has(r.reply, "na")),
    ("Trong danh sách đi chợ còn thiếu gì?", "read",
     lambda r: r.kind == "answer" and has(r.reply, "sữa", "dầu") and not has(r.reply, "gạo")),
    ("Nhà mình có mấy thành viên và ai là trẻ em?", "read",
     lambda r: r.kind == "answer" and has(r.reply, "4", "na", "bin")),
    ("Việc nào của mẹ Lan hạn trong tuần này?", "read",
     lambda r: r.kind == "answer" and has(r.reply, "tiền điện") and not has(r.reply, "họp phụ huynh")),
    ("Thêm sữa chua và 2 chục trứng vào danh sách đi chợ", "propose",
     lambda r: r.kind == "proposal" and has(added(r), "sữa chua", "trứng")),
    ("Mai đi chợ nhớ mua rau muống với cà chua giúp mình", "propose",
     lambda r: r.kind == "proposal" and has(added(r), "rau muống", "cà chua")),
    ("Danh sách đã có sữa tươi rồi, thêm bột giặt và nước rửa chén nhé", "propose",
     lambda r: r.kind == "proposal" and has(added(r), "bột giặt", "nước rửa chén") and not has(added(r), "sữa tươi")),
    ("Thêm cái đó vào danh sách nhé", "ambiguous",
     lambda r: r.kind == "clarification" or (r.kind == "answer" and "?" in r.reply)),
    ("Giao việc cho bé", "ambiguous",
     lambda r: r.kind == "clarification" or (r.kind == "answer" and "?" in r.reply)),
]


@dataclass
class Row:
    question: str
    kind_expected: str
    kind: str
    ok: bool
    model_requests: int
    tool_calls: int
    app_gets: int
    seconds: float
    note: str


async def run_case(model: Any, question: str, check: Check, methods: list[str], gets: list[int]) -> tuple[Row, Any]:
    gets[0] = 0

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        gets[0] += 1
        data = DATA.get(request.url.path)
        return httpx.Response(200, json=data) if data is not None else httpx.Response(404, json={})

    started = time.monotonic()
    try:
        r = await asyncio.wait_for(
            run_turn(
                model,
                TurnInput(question, [], UserInfo("m2", "Mẹ Lan", "member"), TOKEN, "2026-10-10", "Thứ Bảy"),
                app_base_url=APP, limits=TurnLimits(), transport=httpx.MockTransport(handler),
            ),
            90,
        )
    except Exception as e:  # ghi nguyên văn lỗi để đánh giá nhà cung cấp/model
        return Row(question, "", "error", False, 0, 0, gets[0], time.monotonic() - started,
                   f"{type(e).__name__}: {str(e)[:160]}"), None
    note = (r.question or r.reply).replace("\n", " ")[:110]
    if r.operations:
        note = f"ops={added(r)!r}"
    return Row(question, "", r.kind, check(r), r.usage["requests"], r.usage["toolCalls"], gets[0],
               time.monotonic() - started, note), r


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", help="ghi bảng markdown vào file này")
    ap.add_argument("--only", type=int, nargs="*", help="chỉ chạy các câu số này (1-10)")
    args = ap.parse_args()
    need = ["AGENT_LLM_BASE_URL", "AGENT_LLM_API_KEY", "AGENT_LLM_MODEL"]
    if any(not os.environ.get(k) for k in need):
        print("Thiếu env:", ", ".join(need))
        return 2
    settings = Settings(AGENT_SHARED_SECRET="s" * 40)  # type: ignore[call-arg]
    model = build_model(settings)
    methods: list[str] = []
    gets = [0]
    rows: list[Row] = []
    for n, (q, kind, check) in enumerate(CASES, 1):
        if args.only and n not in args.only:
            continue
        row, _ = await run_case(model, q, check, methods, gets)
        row.kind_expected = kind
        rows.append(row)
        print(f"{n:2} {'PASS' if row.ok else 'FAIL'} {kind:9} -> {row.kind:13} req={row.model_requests} "
              f"tools={row.tool_calls} gets={row.app_gets} {row.seconds:5.1f}s  {q[:40]} | {row.note}")
    passed = sum(r.ok for r in rows)
    writes = [m for m in methods if m != "GET"]
    print(f"TOTAL {passed}/{len(rows)}  model={settings.llm_model}  app_requests={len(methods)} writes={len(writes)}")
    if args.report:
        lines = [
            "| # | Câu hỏi | Loại | Kết quả | Kind | Model req | Tool call | GET app | Giây | Ghi chú |",
            "| :-- | :-- | :-- | :-- | :-- | --: | --: | --: | --: | :-- |",
        ]
        for n, r in enumerate(rows, 1):
            lines.append(f"| {n} | {r.question} | {r.kind_expected} | {'PASS' if r.ok else 'FAIL'} | {r.kind} | "
                         f"{r.model_requests} | {r.tool_calls} | {r.app_gets} | {r.seconds:.1f} | "
                         f"{r.note.replace('|', '/')} |")
        lines.append("")
        lines.append(f"**Model `{settings.llm_model}`: {passed}/{len(rows)}** — request tới app: {len(methods)}, "
                     f"trong đó method ≠ GET: {len(writes)}.")
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if not writes else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
