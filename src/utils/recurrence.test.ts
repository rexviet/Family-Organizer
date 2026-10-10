/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from "vitest";
import { expandRecurringOccurrences, parsePlanDate, RecurringPlanLike } from "./recurrence.js";
// Bộ case dùng chung với bản Python (agent/src/family_agent/harness/recurrence.py,
// agent/tests/unit/test_recurrence.py) — sửa hành vi thì sửa case ở file JSON, cả hai phía phải xanh.
import cases from "./recurrence.cases.json";

const d = (s: string) => new Date(`${s}T00:00:00`);
const iso = (x: Date) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
const expand = (plan: Partial<RecurringPlanLike>, from: string, to: string) =>
  expandRecurringOccurrences(
    { isRecurring: true, startDate: "2026-07-01", ...plan } as RecurringPlanLike,
    d(from), d(to)
  ).map(iso);

describe("parsePlanDate", () => {
  for (const c of cases.parsePlanDate) {
    it(c.name, () => {
      const out = parsePlanDate((c.input ?? undefined) as string | undefined);
      expect(out === null ? null : iso(out)).toBe(c.expected);
    });
  }
});

const groups = [...new Set(cases.expand.map(c => c.group))];
for (const group of groups) {
  describe(`expandRecurringOccurrences — ${group}`, () => {
    for (const c of cases.expand.filter(x => x.group === group)) {
      it(c.name, () => {
        const out = expand(c.plan as Partial<RecurringPlanLike>, c.from, c.to);
        if ("expected" in c) {
          expect(out).toEqual(c.expected);
        } else {
          expect(out).toHaveLength(c.expectedCount as number);
          expect(out[0]).toBe(c.expectedFirst);
          expect(out[out.length - 1]).toBe(c.expectedLast);
        }
      });
    }
  });
}
