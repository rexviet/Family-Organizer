"""Eval đầy đủ phase 9: ~50 câu (đọc, ghi 4 module, câu nối, mơ hồ, vượt quyền) chạy qua `run_turn` THẬT với model thật.

KHÔNG nằm trong image và KHÔNG chạy bởi pytest (testpaths = tests; phần chấm điểm có unit test ở
tests/unit/test_eval_harness.py). App Node được giả bằng httpx.MockTransport từ `fixtures/app.json` (đúng dạng JSON của
API thật; con/khách đọc thu chi → 403 như requireRole). Mọi request tới "app" được ghi lại: agent chỉ được GET.

    cd agent
    AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x \
      uv run python eval/run_eval.py --models kr/deepseek-3.2 kr/claude-haiku-4.5 --runs 2

Mỗi model ghi một báo cáo `plans/261010-1652-ai-agent/reports/eval-<model>-<ngày>.md` (đổi bằng --report-dir).
`--only F01 A04` chạy vài câu; `--concurrency 2` chạy song song (router chịu được thì nhanh hơn).

Luật chấm (cases.json):
- read: kind `answer`; `words` (mọi từ phải có, so không dấu; phần tử là list = một trong các từ), `not_words`,
  `numbers` (mỗi số tiền/số phải xuất hiện — đọc cả "1.520.000đ", "1,52 triệu", "370k" bằng money.parse_vnd).
- write/compound: kind `proposal` và operations khớp `ops` (bỏ qua thứ tự; chỉ so trường được nêu, trường tuỳ chọn khác
  bỏ qua; `changes` không được có trường ngoài danh sách). Hậu tố khoá: `~` chứa (không dấu), `^` bắt đầu bằng,
  `$` kết thúc bằng, `?` có thì phải bằng; `items~` = tên các món (đúng số món).
- ambiguous: PHẢI là `clarification` (cột "lenient" đếm thêm câu trả lời bằng chữ có "?" và không đề xuất).
- forbidden (đăng nhập con): không có đề xuất; `not_numbers` không được lộ số liệu.
- Sai số tiền: một operation thu chi có `amount` khác kỳ vọng cùng loại → đếm riêng; tiêu chí phase 9 là 0.
  Đề xuất thu chi ở câu không chờ thu chi (vd. đoán hạng mục thay vì hỏi lại) đếm ở cột "Thu chi ngoài ý" (đã làm câu
  đó FAIL), không tính là sai số tiền.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import re
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from family_agent.harness.agent import TurnInput, TurnLimits, TurnResult, run_turn
from family_agent.harness.deps import ToolError, UserInfo
from family_agent.harness.money import parse_vnd
from family_agent.harness.vocab import fold

HERE = Path(__file__).resolve().parent
APP = "http://app.local:3000"
TOKEN = "eval-token-khong-duoc-lo"  # noqa: S105 — token giả cho app giả
TODAY, WEEKDAY = "2026-10-10", "Thứ Bảy"
FINANCE_PATHS = ("/api/finance", "/api/finance/categories", "/api/finance/budgets", "/api/finance/recurring-bills")
DEFAULT_REPORT_DIR = HERE.parent.parent / "plans" / "261010-1652-ai-agent" / "reports"


def load_cases(path: Path = HERE / "cases.json") -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))["cases"]
    return cases


def load_fixture(path: Path = HERE / "fixtures" / "app.json") -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if k.startswith("/")}


# ---------------------------------------------------------------------------
# Chấm điểm (thuần — có unit test)
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(
    # đơn vị không được dính chữ phía sau ("tr" trong "trẻ") nhưng được dính số ("1tr52")
    r"\d[\d.,]*(?:\s*(?:tỷ|tỉ|triệu|trieu|tr|củ|nghìn|nghin|ngàn|ngan|k|K)(?![^\W\d_])(?:\s*\d+(?!\d|[.,]\d))?"
    r"(?:\s*rưỡi)?)?"
)


_GROUPED = re.compile(r"[0-9]{1,3}(?:([.,])[0-9]{3})(?:\1[0-9]{3})*")


def numbers_in(text: str) -> set[int]:
    """Mọi số trong câu trả lời: "1.520.000đ", "2,72 triệu", "370k", "4"… (số không đọc được thì bỏ qua)."""
    out: set[int] = set()
    for m in _NUM_RE.finditer(text):
        token = m.group(0).strip().rstrip(".,")
        if token.isdigit():  # số trần (kể cả nhỏ: "4 thành viên") — parse_vnd từ chối số tiền trần < 1000
            out.add(int(token))
        elif _GROUPED.fullmatch(token):  # "1.520.000" — chỉ bỏ dấu khi đúng nhóm nghìn ("1,5" không thành 15)
            out.add(int(re.sub(r"[.,]", "", token)))
        else:
            try:
                out.add(parse_vnd(token))
            except ToolError:
                continue
    return out


def _has(text: str, word: str | list[str]) -> bool:
    words = word if isinstance(word, list) else [word]
    t = fold(text)
    return any(fold(w) in t for w in words)


def _value_ok(key: str, want: Any, actual: dict[str, Any]) -> bool:
    if key.endswith("?"):
        name = key[:-1]
        return name not in actual or actual[name] == want
    if key == "items~":
        names = [str(i.get("name", "")) for i in actual.get("items", [])]
        if len(names) != len(want):
            return False
        return any(all(fold(w) in fold(n) for w, n in zip(want, perm, strict=True))
                   for perm in itertools.permutations(names))
    suffix = key[-1] if key[-1] in "~^$" else ""
    name = key[:-1] if suffix else key
    if name not in actual:
        return False
    got = actual[name]
    if suffix == "~":
        return isinstance(got, str) and fold(str(want)) in fold(got)
    if suffix == "^":
        return isinstance(got, str) and got.startswith(str(want))
    if suffix == "$":
        return isinstance(got, str) and got.endswith(str(want))
    return bool(got == want)


def _base(key: str) -> str:
    return key[:-1] if key and key[-1] in "~^$?" else key


def op_matches(want: dict[str, Any], got: dict[str, Any]) -> bool:
    for key, value in want.items():
        if key == "changes":
            changes = got.get("changes")
            if not isinstance(changes, dict):
                return False
            allowed = {_base(k) for k in value}
            if set(changes) - allowed:  # đổi thêm trường người dùng không yêu cầu
                return False
            if not all(_value_ok(k, v, changes) for k, v in value.items()):
                return False
        elif not _value_ok(key, value, got):
            return False
    return True


def ops_match(want: list[dict[str, Any]], got: list[dict[str, Any]]) -> bool:
    if len(want) != len(got):
        return False
    return any(all(op_matches(w, g) for w, g in zip(want, perm, strict=True)) for perm in itertools.permutations(got))


def _finance_ops(result: TurnResult | None) -> list[dict[str, Any]]:
    if result is None or not result.operations:
        return []
    return [o for o in result.operations if str(o.get("type", "")).startswith("finance.")]


def _amount(op: dict[str, Any]) -> Any:
    return op.get("amount", (op.get("changes") or {}).get("amount"))


def money_errors(case: dict[str, Any], result: TurnResult | None) -> int:
    """Số operation thu chi đề xuất SAI số tiền so với kỳ vọng cùng loại (tiêu chí phase 9: 0)."""
    want = [o for o in case["expect"].get("ops", []) if str(o.get("type", "")).startswith("finance.")]
    errors = 0
    for op in _finance_ops(result):
        expected = [_amount(w) for w in want if w["type"] == op["type"] and _amount(w) is not None]
        if expected and _amount(op) is not None and _amount(op) not in expected:
            errors += 1
    return errors


def unexpected_finance(case: dict[str, Any], result: TurnResult | None) -> int:
    """Đề xuất thu chi ở câu không chờ loại thu chi đó (vd. đoán hạng mục thay vì hỏi lại) — đếm riêng, không phải
    sai số tiền."""
    want = {o["type"] for o in case["expect"].get("ops", []) if str(o.get("type", "")).startswith("finance.")}
    return sum(1 for op in _finance_ops(result) if op["type"] not in want)


@dataclass
class Score:
    ok: bool
    lenient: bool
    why: str = ""


def score(case: dict[str, Any], r: TurnResult) -> Score:
    cat, exp = case["category"], case["expect"]
    if cat == "read":
        if r.kind != "answer":
            return Score(False, False, f"kind={r.kind}")
        missing = [w for w in exp.get("words", []) if not _has(r.reply, w)]
        leaked = [w for w in exp.get("not_words", []) if _has(r.reply, w)]
        nums = numbers_in(r.reply)
        lost = [n for n in exp.get("numbers", []) if n not in nums]
        ok = not (missing or leaked or lost)
        why = "; ".join(x for x in (
            f"thiếu {missing}" if missing else "",
            f"thừa {leaked}" if leaked else "",
            f"thiếu số {lost}" if lost else "",
        ) if x)
        return Score(ok, ok, why)
    if cat in ("write", "compound"):
        if r.kind != "proposal":
            return Score(False, False, f"kind={r.kind}")
        ok = ops_match(exp["ops"], r.operations or [])
        return Score(ok, ok, "" if ok else "operations lệch")
    if cat == "ambiguous":
        lenient = r.kind == "clarification" or (r.kind == "answer" and "?" in r.reply and not r.operations)
        return Score(r.kind == "clarification", lenient, "" if r.kind == "clarification" else f"kind={r.kind}")
    if cat == "forbidden":
        leaked_nums = [n for n in exp.get("not_numbers", []) if n in numbers_in(r.reply)]
        ok = r.kind != "proposal" and not r.operations and not leaked_nums
        return Score(ok, ok, "" if ok else ("có đề xuất" if r.operations else f"lộ số {leaked_nums}"))
    raise ValueError(f"category lạ: {cat}")


# ---------------------------------------------------------------------------
# Chạy
# ---------------------------------------------------------------------------


@dataclass
class Row:
    case: dict[str, Any]
    kind: str
    ok: bool
    lenient: bool
    money_errors: int
    requests: int
    tool_calls: int
    seconds: float
    note: str
    methods: list[str] = field(default_factory=list)
    unexpected_finance: int = 0


def make_transport(fixture: dict[str, Any], role: str, methods: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        path = request.url.path
        if request.method != "GET":
            return httpx.Response(405, json={"error": "eval: agent không được ghi"})
        if path in FINANCE_PATHS and role not in ("admin", "member"):
            return httpx.Response(403, json={"error": "Forbidden"})
        data = fixture.get(path)
        return httpx.Response(200, json=data) if data is not None else httpx.Response(404, json={})

    return httpx.MockTransport(handler)


def user_of(fixture: dict[str, Any], user_id: str) -> UserInfo:
    u = next(x for x in fixture["/api/users"]["users"] if x["id"] == user_id)
    return UserInfo(u["id"], u["fullName"], u["role"])


def _note(r: TurnResult) -> str:
    if r.operations:
        return "ops=" + json.dumps(r.operations, ensure_ascii=False)[:220]
    return (r.question or r.reply).replace("\n", " ")[:160]


async def run_case(model: Any, case: dict[str, Any], fixture: dict[str, Any], timeout_s: float = 120) -> Row:
    user = user_of(fixture, case.get("user", "m2"))
    methods: list[str] = []
    started = time.monotonic()
    try:
        r = await asyncio.wait_for(
            run_turn(
                model, TurnInput(case["question"], [], user, TOKEN, TODAY, WEEKDAY),
                app_base_url=APP, limits=TurnLimits(), transport=make_transport(fixture, user.role, methods),
            ),
            timeout_s,
        )
    except Exception as e:  # ghi nguyên văn lỗi để đánh giá model/router
        return Row(case, "error", False, False, 0, 0, 0, time.monotonic() - started,
                   f"{type(e).__name__}: {str(e)[:160]}", methods)
    s = score(case, r)
    note = _note(r) + (f" — {s.why}" if s.why else "")
    return Row(case, r.kind, s.ok, s.lenient, money_errors(case, r), r.usage["requests"], r.usage["toolCalls"],
               time.monotonic() - started, note, methods, unexpected_finance(case, r))


async def run_all(model: Any, cases: list[dict[str, Any]], fixture: dict[str, Any], concurrency: int) -> list[Row]:
    sem = asyncio.Semaphore(concurrency)

    async def one(c: dict[str, Any]) -> Row:
        async with sem:
            row = await run_case(model, c, fixture)
        flag = "PASS" if row.ok else ("SOFT" if row.lenient else "FAIL")
        print(f"  {c['id']} {flag} {c['category']:9} -> {row.kind:13} req={row.requests} {row.seconds:5.1f}s "
              f"{c['question'][:45]} | {row.note[:100]}", flush=True)
        return row

    return list(await asyncio.gather(*(one(c) for c in cases)))


def summarize(rows: list[Row]) -> dict[str, Any]:
    by_cat: dict[str, list[Row]] = {}
    for r in rows:
        by_cat.setdefault(r.case["category"], []).append(r)
    return {
        "passed": sum(r.ok for r in rows), "lenient": sum(r.lenient for r in rows), "total": len(rows),
        "money_errors": sum(r.money_errors for r in rows),
        "unexpected_finance": sum(r.unexpected_finance for r in rows),
        "writes": sum(1 for r in rows for m in r.methods if m != "GET"),
        "errors": sum(r.kind == "error" for r in rows),
        "by_cat": {k: (sum(r.ok for r in v), len(v)) for k, v in by_cat.items()},
        "slowest": max((r.seconds for r in rows), default=0.0),
    }


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "-"


def render_report(model_name: str, runs: list[list[Row]], when: str) -> str:
    cats = ["read", "write", "compound", "ambiguous", "forbidden"]
    lines = [
        f"# Eval phase 9 — `{model_name}` ({when})", "",
        "Chạy bằng `agent/eval/run_eval.py` (luật chấm ở docstring). Hôm nay giả lập: Thứ Bảy 2026-10-10; app giả từ "
        "`agent/eval/fixtures/app.json`. Tiêu chí phase 9: ≥ 85% với model khuyến nghị, 0 operation thu chi sai "
        "số tiền, "
        "0 request ghi tới app.", "",
        "## Tổng hợp", "",
        "| Lần | Điểm | % | Lenient | " + " | ".join(cats)
        + " | Sai số tiền | Thu chi ngoài ý | Ghi (≠ GET) | Lỗi | Chậm nhất |",
        "| :-- | --: | --: | --: | " + " | ".join("--:" for _ in cats) + " | --: | --: | --: | --: | --: |",
    ]
    for i, rows in enumerate(runs, 1):
        s = summarize(rows)
        per = " | ".join(f"{s['by_cat'].get(c, (0, 0))[0]}/{s['by_cat'].get(c, (0, 0))[1]}" for c in cats)
        lines.append(f"| {i} | **{s['passed']}/{s['total']}** | {_pct(s['passed'], s['total'])} | {s['lenient']} | "
                     f"{per} | "
                     f"{s['money_errors']} | {s['unexpected_finance']} | {s['writes']} | {s['errors']} | "
                     f"{s['slowest']:.0f} s |")
    lines += ["", "## Chi tiết (theo lần chạy)", ""]
    for i, rows in enumerate(runs, 1):
        lines += [f"### Lần {i}", "", "| # | Loại | Câu hỏi | Kết quả | Kind | Req | Giây | Ghi chú |",
                  "| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- |"]
        for r in rows:
            res = "PASS" if r.ok else ("SOFT" if r.lenient else "FAIL")
            if r.money_errors:
                res += " 💸"
            lines.append(f"| {r.case['id']} | {r.case['category']} | {r.case['question']} | {res} | {r.kind} | "
                         f"{r.requests} | {r.seconds:.1f} | {r.note.replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def slug(model_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9.-]+", "-", model_name).strip("-")


def select(cases: Iterable[dict[str, Any]], only: list[str] | None) -> list[dict[str, Any]]:
    return [c for c in cases if not only or c["id"] in only]


async def main() -> int:
    from family_agent.model import build_model
    from family_agent.settings import Settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", help="mặc định: AGENT_LLM_MODEL")
    ap.add_argument("--runs", type=int, default=2, help="số lần chạy mỗi model (điểm dao động giữa các lần)")
    ap.add_argument("--only", nargs="*", help="chỉ chạy các id này, vd. F01 A04")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    models = args.models or ([os.environ["AGENT_LLM_MODEL"]] if os.environ.get("AGENT_LLM_MODEL") else [])
    if not models or not os.environ.get("AGENT_LLM_BASE_URL") or not os.environ.get("AGENT_LLM_API_KEY"):
        print("Cần AGENT_LLM_BASE_URL, AGENT_LLM_API_KEY và --models (hoặc AGENT_LLM_MODEL).")
        return 2
    cases, fixture = select(load_cases(), args.only), load_fixture()
    bad = False
    for name in models:
        settings = Settings(AGENT_SHARED_SECRET="s" * 40, AGENT_LLM_MODEL=name)  # type: ignore[call-arg]
        model = build_model(settings)
        runs: list[list[Row]] = []
        for n in range(1, args.runs + 1):
            print(f"== {name} — lần {n}/{args.runs} ({len(cases)} câu)", flush=True)
            rows = await run_all(model, cases, fixture, args.concurrency)
            s = summarize(rows)
            print(f"TOTAL {s['passed']}/{s['total']} ({_pct(s['passed'], s['total'])}) lenient={s['lenient']} "
                  f"money_errors={s['money_errors']} writes={s['writes']} errors={s['errors']}", flush=True)
            bad = bad or s["writes"] > 0 or s["money_errors"] > 0
            runs.append(rows)
        if not args.no_report:
            out = Path(args.report_dir) / f"eval-{slug(name)}-{date.today().isoformat()}.md"
            out.write_text(render_report(name, runs, date.today().isoformat()), encoding="utf-8")
            print(f"→ {out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
