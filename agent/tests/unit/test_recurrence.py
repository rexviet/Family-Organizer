"""Bản Python của expandRecurringOccurrences — cùng case với src/utils/recurrence.test.ts (file JSON dùng chung)."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from family_agent.harness.recurrence import expand_recurring_occurrences, parse_plan_date

CASES: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parents[3] / "src" / "utils" / "recurrence.cases.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES["parsePlanDate"], ids=lambda c: c["name"])
def test_parse_plan_date(case: dict[str, Any]) -> None:
    out = parse_plan_date(case["input"])
    assert (out.isoformat() if out else None) == case["expected"]


@pytest.mark.parametrize("case", CASES["expand"], ids=lambda c: f"{c['group']} — {c['name']}")
def test_expand(case: dict[str, Any]) -> None:
    plan = {"isRecurring": True, "startDate": "2026-07-01", **case["plan"]}
    out = [
        d.isoformat()
        for d in expand_recurring_occurrences(plan, date.fromisoformat(case["from"]), date.fromisoformat(case["to"]))
    ]
    if "expected" in case:
        assert out == case["expected"]
    else:
        assert len(out) == case["expectedCount"]
        assert out[0] == case["expectedFirst"]
        assert out[-1] == case["expectedLast"]


def test_weekdays_khong_phai_list_thi_dung_thu_mac_dinh() -> None:
    plan = {"isRecurring": True, "startDate": "2026-07-01", "recurrenceType": "weekly", "recurrenceWeekdays": "3"}
    out = expand_recurring_occurrences(plan, date(2026, 7, 1), date(2026, 7, 15))
    assert [d.isoformat() for d in out] == ["2026-07-01", "2026-07-08", "2026-07-15"]  # mặc định: Thứ Tư
