/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, expect, it } from "vitest";
import {
  CONTRACT_VERSION,
  canonical,
  fingerprint,
  planHash,
  validateOperations,
} from "./agentContract.js";
// Bộ vector dùng chung với phía Python (agent/contracts/gen_vectors.py tính độc lập).
import vectorsJson from "../agent/contracts/vectors.json";

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- vector có nhiều hình dạng
const vectors: any = vectorsJson;

describe("CONTRACT_VERSION", () => {
  it("lấy từ schema và khớp với vectors", () => {
    expect(CONTRACT_VERSION).toBe(1);
    expect(vectors.contractVersion).toBe(CONTRACT_VERSION);
  });
});

describe("canonical", () => {
  for (const v of vectors.canonical) {
    it(`khớp vector: ${v.name}`, () => {
      expect(canonical(v.value)).toBe(v.canonical);
    });
  }

  it("bỏ key có giá trị undefined (như khi JSON hoá)", () => {
    expect(canonical({ a: 1, b: undefined })).toBe('{"a":1}');
  });

  it("từ chối số thực, NaN, Infinity và số nguyên vượt 2^53-1", () => {
    expect(() => canonical({ a: 1.5 })).toThrow();
    expect(() => canonical([NaN])).toThrow();
    expect(() => canonical([Infinity])).toThrow();
    expect(() => canonical(2 ** 53)).toThrow();
  });

  it("từ chối chuỗi có surrogate lẻ (không mã hoá UTF-8 được)", () => {
    expect(() => canonical("a\ud800b")).toThrow();
    expect(() => canonical({ ["\udc00"]: 1 })).toThrow();
  });

  it("từ chối kiểu không phải JSON", () => {
    expect(() => canonical(() => 1)).toThrow();
    expect(() => canonical(new Date())).toThrow();
    expect(() => canonical(10n)).toThrow();
  });
});

describe("planHash", () => {
  for (const v of vectors.planHash) {
    it(`khớp vector: ${v.name}`, () => {
      expect(canonical(v.operations)).toBe(v.canonical);
      expect(planHash(v.operations)).toBe(v.planHash);
    });
  }

  it("thứ tự operation có nghĩa → hash khác", () => {
    const [a, b] = vectors.planHash.slice(-2);
    expect(a.planHash).not.toBe(b.planHash);
  });
});

describe("fingerprint", () => {
  for (const v of vectors.fingerprint) {
    it(`khớp vector: ${v.name}`, () => {
      expect(fingerprint(v.kind, v.record)).toBe(v.fingerprint);
    });
  }

  it("chỉ phụ thuộc các trường chính", () => {
    const byName = (n: string) => vectors.fingerprint.find((v: any) => v.name.startsWith(n));
    expect(byName("giao dịch chỉ khác creatorId").fingerprint).toBe(byName("giao dịch chi đủ trường").fingerprint);
    expect(byName("lịch chỉ khác màu").fingerprint).not.toBe(byName("lịch lặp có recurrenceWeekdays").fingerprint);
  });

  it("từ chối loại bản ghi lạ", () => {
    expect(() => fingerprint("task" as any, {})).toThrow();
  });
});

describe("validateOperations", () => {
  for (const v of vectors.planHash) {
    it(`chấp nhận vector hợp lệ: ${v.name}`, () => {
      const r = validateOperations(v.operations);
      expect(r.errors).toEqual([]);
      expect(r.ok).toBe(true);
    });
  }

  for (const v of vectors.invalid) {
    it(`từ chối: ${v.name}`, () => {
      const r = validateOperations(v.operations);
      expect(r.ok).toBe(false);
      expect(r.errors.length).toBeGreaterThan(0);
    });
  }

  it("từ chối đầu vào không phải mảng", () => {
    expect(validateOperations(null).ok).toBe(false);
    expect(validateOperations({ type: "shopping.add" }).ok).toBe(false);
  });

  it("báo lỗi có đường dẫn tới trường sai", () => {
    const r = validateOperations([
      { type: "finance.create", txType: "expense", amount: -1, category: "x", date: "2026-10-09", description: "" },
    ]);
    expect(r.errors.some((e) => e.path === "$[0].amount")).toBe(true);
  });

  it("type lạ báo một lỗi rõ ràng thay vì lỗi của cả 12 nhánh", () => {
    const r = validateOperations([{ type: "shopping.toggle" }]);
    expect(r.errors).toHaveLength(1);
    expect(r.errors[0].path).toBe("$[0].type");
  });

  it("đúng 30 món đi chợ trong một proposal thì được", () => {
    const items = (n: number, p: string) => Array.from({ length: n }, (_, i) => ({ name: `${p}${i}` }));
    const r = validateOperations([
      { type: "shopping.add", items: items(20, "a") },
      { type: "shopping.add", items: items(10, "b") },
    ]);
    expect(r.ok).toBe(true);
  });

  it("độ dài chuỗi tính theo code point (emoji là 1 ký tự)", () => {
    const r = validateOperations([{ type: "shopping.add", items: [{ name: "🥚".repeat(100) }] }]);
    expect(r.ok).toBe(true);
  });

  // Đầu vào thật đến từ JSON.parse — key "__proto__" khi đó là thuộc tính riêng.
  it("từ chối key trùng tên thuộc tính của Object.prototype (__proto__, constructor…)", () => {
    const cases = [
      '[{"type":"task.update","taskId":"t1","changes":{"title":"a","__proto__":{"status":"completed"}},"base":{"updatedAt":"x"}}]',
      '[{"type":"task.update","taskId":"t1","changes":{"__proto__":{"status":"completed"}},"base":{"updatedAt":"x"}}]',
      '[{"type":"shopping.add","items":[{"name":"a","toString":"x","hasOwnProperty":1}]}]',
      '[{"type":"task.delete","taskId":"t1","base":{"updatedAt":"x"},"constructor":{}}]',
    ];
    for (const c of cases) expect(validateOperations(JSON.parse(c)).ok, c).toBe(false);
  });

  it("thiếu trường bắt buộc không được bù bằng prototype", () => {
    const op = Object.create({ base: { updatedAt: "x" } });
    Object.assign(op, { type: "task.delete", taskId: "t1" });
    expect(validateOperations([op]).ok).toBe(false);
  });

  it("trả về bản sao chỉ gồm dữ liệu, sửa đầu vào sau khi kiểm không ảnh hưởng", () => {
    const input = [{ type: "task.update", taskId: "t1", changes: { title: "a" }, base: { updatedAt: "x" } }];
    const r = validateOperations(input);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    (input[0].changes as Record<string, unknown>).status = "completed";
    expect(r.operations[0]).toEqual({ type: "task.update", taskId: "t1", changes: { title: "a" }, base: { updatedAt: "x" } });
    expect(planHash(r.operations)).toBe(planHash(JSON.parse(JSON.stringify(r.operations))));
  });

  it("từ chối chuỗi mà canonical không mã hoá được (surrogate lẻ)", () => {
    const r = validateOperations([{ type: "shopping.add", items: [{ name: "a\ud800" }] }]);
    expect(r.ok).toBe(false);
  });

  it("mảng quá dài dừng sớm, không quét từng phần tử (chống DoS)", () => {
    const big = Array.from({ length: 200_000 }, (_, i) => i);
    const t = Date.now();
    const r = validateOperations([
      { type: "plan.create", title: "x", startDate: "2026-10-12 18:00", endDate: "2026-10-12 19:00", recurrenceWeekdays: big },
    ]);
    expect(r.ok).toBe(false);
    expect(Date.now() - t).toBeLessThan(200);
    expect(r.errors.length).toBeLessThanOrEqual(50);
  });

  it("số lỗi trả về có giới hạn", () => {
    const items = Array.from({ length: 20 }, () => ({ name: "", a: 1, b: 2, c: 3 }));
    const ops = Array.from({ length: 10 }, () => ({ type: "shopping.add", items }));
    expect(validateOperations(ops).errors.length).toBeLessThanOrEqual(50);
  });
});
