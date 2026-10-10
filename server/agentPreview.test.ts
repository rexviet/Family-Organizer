/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from "vitest";
import { buildPreview, type PreviewContext } from "./agentPreview.js";
import type { AgentOperation } from "./agentContract.js";

const ctx: PreviewContext = {
  users: [{ id: "u_bin", fullName: "Bin" }, { id: "u_lan", fullName: "Lan" }],
  shoppingItems: [{ id: "s1", name: "Sữa tươi", quantity: "2 hộp" }],
  tasks: [{ id: "t1", title: "Đổ rác", dueDate: "2026-10-10 18:00", assigneeId: null, priority: "medium", status: "todo" }],
  plans: [{ id: "p1", title: "Họp phụ huynh", startDate: "2026-10-12 08:00", endDate: "2026-10-12 10:00" }],
  transactions: [{ id: "x1", type: "expense", amount: 250000, category: "food", date: "2026-10-09", description: "Ăn trưa" }],
  categoryLabel: (id) => ({ food: "Ăn uống", shopping: "Mua sắm" } as Record<string, string>)[id] ?? id,
};

const one = (op: AgentOperation) => buildPreview([op], ctx)[0];
const B = { updatedAt: "2026-10-10T00:00:00.000Z" };
const F = { fingerprint: "a".repeat(64) };

describe("buildPreview — đi chợ", () => {
  it("shopping.add: liệt kê món + số lượng", () => {
    expect(one({ type: "shopping.add", items: [{ name: "sữa", quantity: "2 hộp" }, { name: "trứng" }] }))
      .toEqual({ icon: "🛒", text: "Thêm 2 món: sữa (2 hộp), trứng", tone: "add" });
  });
  it("shopping.add nhiều món: rút gọn sau 5 món", () => {
    const items = Array.from({ length: 8 }, (_, i) => ({ name: `m${i}` }));
    expect(one({ type: "shopping.add", items }).text).toBe("Thêm 8 món: m0, m1, m2, m3, m4 và 3 món khác");
  });
  it("set_purchased lấy tên thật từ DB", () => {
    expect(one({ type: "shopping.set_purchased", itemId: "s1", purchased: true, base: B }))
      .toEqual({ icon: "✅", text: "Đánh dấu đã mua: Sữa tươi (2 hộp)", tone: "edit" });
    expect(one({ type: "shopping.set_purchased", itemId: "s1", purchased: false, base: B }).text)
      .toBe("Đánh dấu chưa mua: Sữa tươi (2 hộp)");
  });
  it("delete: tone delete; món không còn → ghi rõ", () => {
    expect(one({ type: "shopping.delete", itemId: "s1", base: B }))
      .toEqual({ icon: "🗑️", text: "Xoá khỏi danh sách đi chợ: Sữa tươi (2 hộp)", tone: "delete" });
    expect(one({ type: "shopping.delete", itemId: "nope", base: B }).text).toContain("(không còn tồn tại)");
  });
});

describe("buildPreview — việc", () => {
  it("task.create: giao + hạn dd/MM HH:mm", () => {
    expect(one({ type: "task.create", title: "Đón con", assigneeId: "u_bin", dueDate: "2026-10-11 17:00" }))
      .toEqual({ icon: "✅", text: 'Tạo việc "Đón con" — giao Bin — 17:00 11/10', tone: "add" });
  });
  it("task.update: hiện cũ → mới", () => {
    expect(one({ type: "task.update", taskId: "t1", base: B, changes: { dueDate: "2026-10-12 18:00", assigneeId: "u_lan" } }))
      .toEqual({ icon: "✏️", text: 'Việc "Đổ rác": hạn 18:00 10/10 → 18:00 12/10; giao (chưa giao) → Lan', tone: "edit" });
  });
  it("task.delete", () => {
    expect(one({ type: "task.delete", taskId: "t1", base: B })).toEqual({ icon: "🗑️", text: 'Xoá việc "Đổ rác"', tone: "delete" });
  });
});

describe("buildPreview — lịch", () => {
  it("plan.create lặp: ghi kiểu lặp + thứ + ngày lặp đến (kèm năm)", () => {
    expect(one({
      type: "plan.create", title: "Học bơi", startDate: "2026-10-13 18:00", endDate: "2027-10-13 19:00",
      recurrenceType: "weekly", recurrenceWeekdays: [2, 4],
    }).text).toBe('Tạo sự kiện "Học bơi" — 18:00 13/10 · lặp hằng tuần (T3, T5) tới 13/10/2027');
    expect(one({
      type: "plan.create", title: "Giỗ ông", startDate: "2026-11-02 09:00", endDate: "2036-11-02 10:00", recurrenceType: "yearly",
    }).text).toBe('Tạo sự kiện "Giỗ ông" — 09:00 02/11 · lặp hằng năm tới 02/11/2036');
  });
  it("plan.create / update / delete", () => {
    expect(one({ type: "plan.create", title: "Sinh nhật", startDate: "2026-10-20 18:00", endDate: "2026-10-20 21:00" }))
      .toEqual({ icon: "📅", text: 'Tạo sự kiện "Sinh nhật" — 18:00 20/10 → 21:00 20/10', tone: "add" });
    expect(one({ type: "plan.update", planId: "p1", base: F, changes: { title: "Họp lớp" } }))
      .toEqual({ icon: "✏️", text: 'Sự kiện "Họp phụ huynh": tên Họp phụ huynh → Họp lớp', tone: "edit" });
    expect(one({ type: "plan.delete", planId: "p1", base: F }))
      .toEqual({ icon: "🗑️", text: 'Xoá sự kiện "Họp phụ huynh" — 08:00 12/10', tone: "delete" });
  });
});

describe("buildPreview — thu chi", () => {
  it("finance.create / update / delete với tiền vi-VN và hạng mục", () => {
    expect(one({ type: "finance.create", txType: "expense", amount: 1250000, category: "shopping", date: "2026-10-10", description: "Giày" }))
      .toEqual({ icon: "💸", text: "Ghi khoản chi 1.250.000₫ · Mua sắm · 10/10 — Giày", tone: "add" });
    expect(one({ type: "finance.create", txType: "income", amount: 5000, category: "food", date: "2026-10-10", description: "x" }).icon).toBe("💰");
    expect(one({ type: "finance.update", txId: "x1", base: F, changes: { amount: 300000 } }))
      .toEqual({ icon: "✏️", text: 'Khoản chi "Ăn trưa": số tiền 250.000₫ → 300.000₫', tone: "edit" });
    expect(one({ type: "finance.delete", txId: "x1", base: F }))
      .toEqual({ icon: "🗑️", text: "Xoá khoản chi 250.000₫ · Ăn uống · 09/10", tone: "delete" });
  });
});

it("mỗi operation đúng một dòng, theo thứ tự", () => {
  const lines = buildPreview([
    { type: "shopping.delete", itemId: "s1", base: B },
    { type: "shopping.add", items: [{ name: "a" }] },
  ], ctx);
  expect(lines.map((l) => l.tone)).toEqual(["delete", "add"]);
});
