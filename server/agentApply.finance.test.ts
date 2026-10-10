/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Apply đề xuất Thu chi (M3): chỉ Admin/Thành viên (như POST/DELETE /api/finance); sửa phải MERGE — trường không
// nêu (kể cả ảnh hoá đơn) giữ nguyên, khác saveTransaction (thay nguyên bản ghi); guard fingerprint; hạng mục chi
// phải còn dùng; xoá giao dịch → xoá file hoá đơn SAU khi ghi xong.

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";
import { AgentStore } from "./agentStore.js";
import { applyProposal, ENABLED_OPERATIONS, type ApplyDeps, type ApplySession } from "./agentApply.js";
import { fingerprint, planHash, type AgentOperation } from "./agentContract.js";
import schemaJson from "../agent/contracts/operations.schema.json";
import type { FamilyOrganizerDB, FinancialTransaction } from "../src/types.js";
import { AccountType, TransactionType, UserRole } from "../src/types.js";

const T0 = Date.parse("2026-10-10T10:00:00.000Z");
const U0 = "2026-10-01T00:00:00.000Z";

const ADMIN: ApplySession = { userId: "u_admin", username: "admin", role: UserRole.ADMIN };
const MEMBER: ApplySession = { userId: "u_mem", username: "mem", role: UserRole.MEMBER };
const KID: ApplySession = { userId: "u_kid", username: "kid", role: UserRole.CHILD };
const GUEST: ApplySession = { userId: "u_guest", username: "guest", role: UserRole.GUEST };

type Mem = Pick<FamilyOrganizerDB,
  "transactions" | "activityLogs" | "customCategories" | "hiddenBuiltinCategories" | "notifications" | "shoppingItems" | "tasks" | "plans" | "users">;

let dir: string;
let store: AgentStore;
let mem: Mem;
let writes: number;
let removed: string[];
let deps: ApplyDeps;

function tx(id: string, extra: Partial<FinancialTransaction> = {}): FinancialTransaction {
  return {
    id, type: TransactionType.EXPENSE, amount: 250000, category: "food", account: AccountType.CASH,
    description: `Giao dịch ${id}`, date: "2026-10-08", creatorId: "u_mem", createdAt: U0,
    receiptImage: `/uploads/receipts/${id}.jpg`, ...extra,
  };
}

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "fo-agent-apply-fin-"));
  store = new AgentStore(path.join(dir, "agent.db"));
  mem = {
    activityLogs: [], notifications: [], shoppingItems: [], tasks: [], plans: [], users: [],
    customCategories: [{ id: "cc_pet", label: "Thú cưng", emoji: "🐶", color: "teal", createdAt: U0, updatedAt: U0 }],
    hiddenBuiltinCategories: ["funeral"],
    transactions: [
      tx("x1"),
      tx("x_income", { type: TransactionType.INCOME, amount: 15000000, category: "Lương tháng", account: AccountType.BANK }),
      tx("x_frac", { amount: 35000.5 }),
      tx("x_admin", { creatorId: "u_admin" }),
    ],
  };
  writes = 0;
  removed = [];
  deps = {
    store,
    now: () => T0,
    applyBatch: (fn) => {
      const copy = structuredClone(mem) as FamilyOrganizerDB;
      const r = fn(copy);
      mem = copy;
      writes++;
      return r;
    },
    removeFiles: (urls) => { removed.push(...urls); },
  };
});
afterEach(() => {
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

function apply(ops: AgentOperation[], s: ApplySession) {
  const p = store.createProposal({ conversationId: "c1", userId: s.userId, operations: ops, planHash: planHash(ops), preview: [] }, T0);
  return { r: applyProposal(deps, p.id, p.planHash, s), id: p.id };
}
const X = (id: string) => mem.transactions.find((t) => t.id === id)!;
const FP = (id: string) => ({ fingerprint: fingerprint("transaction", X(id)) });

it("bật đủ 12 loại operation của hợp đồng (M3)", () => {
  const all = (schemaJson as { $defs: Record<string, unknown> }).$defs;
  const types = Object.keys(all).filter((k) => /^(shopping|task|plan|finance)\./.test(k));
  expect(types).toHaveLength(12);
  for (const t of types) expect(ENABLED_OPERATIONS.has(t as AgentOperation["type"])).toBe(true);
});

describe("finance.create", () => {
  it("ghi khoản chi: người tạo = người duyệt, đúng số tiền, ví mặc định ngân hàng như app, có nhật ký", () => {
    const { r } = apply([{ type: "finance.create", txType: "expense", amount: 250000, category: "food", date: "2026-10-10", description: "Đi chợ" }], MEMBER);
    expect(r).toMatchObject({ ok: true, status: 200, modules: ["FINANCE_UPDATE"] });
    const t = mem.transactions.find((x) => x.description === "Đi chợ")!;
    expect(t).toMatchObject({ type: "expense", amount: 250000, category: "food", date: "2026-10-10", account: "bank", creatorId: "u_mem" });
    expect(t.id).toMatch(/^tx_/);
    expect(t.receiptImage).toBeUndefined();
    expect(mem.activityLogs[0].details).toContain("250.000");
    expect(writes).toBe(1);
  });
  it("khoản thu: hạng mục chữ tự do; hạng mục chi tự thêm (cc_…) và ví chỉ định", () => {
    apply([
      { type: "finance.create", txType: "income", amount: 2000000, category: "Tiền thưởng", date: "2026-10-09", description: "Thưởng", account: "e_wallet" },
      { type: "finance.create", txType: "expense", amount: 1200000, category: "cc_pet", date: "2026-10-09", description: "Tiêm phòng" },
    ], ADMIN);
    expect(mem.transactions.find((x) => x.description === "Thưởng")).toMatchObject({ type: "income", category: "Tiền thưởng", account: "e_wallet" });
    expect(mem.transactions.find((x) => x.description === "Tiêm phòng")?.category).toBe("cc_pet");
  });
  it("hạng mục chi không còn (đã xoá / mặc định đã ẩn / không có) → 422, không ghi", () => {
    for (const category of ["cc_gone", "funeral", "an_vat"]) {
      const { r } = apply([{ type: "finance.create", txType: "expense", amount: 1000, category, date: "2026-10-10", description: "x" }], ADMIN);
      expect(r).toMatchObject({ status: 422, code: "invalid" });
    }
    expect(writes).toBe(0);
  });
  it("ngày không có thật → 422", () => {
    const { r } = apply([{ type: "finance.create", txType: "expense", amount: 1000, category: "food", date: "2026-02-30", description: "x" }], ADMIN);
    expect(r).toMatchObject({ status: 422, code: "invalid" });
  });
  it("Con/Khách → 403, không ghi", () => {
    for (const s of [KID, GUEST]) {
      const { r } = apply([{ type: "finance.create", txType: "expense", amount: 1000, category: "food", date: "2026-10-10", description: "x" }], s);
      expect(r).toMatchObject({ status: 403, code: "forbidden" });
    }
    expect(writes).toBe(0);
  });
});

describe("finance.update — MERGE (red-team P9)", () => {
  it("sửa số tiền: ảnh hoá đơn + mọi trường khác giữ nguyên, không xoá file hoá đơn", () => {
    const before = { ...X("x1") };
    const { r } = apply([{ type: "finance.update", txId: "x1", base: FP("x1"), changes: { amount: 300000 } }], MEMBER);
    expect(r.status).toBe(200);
    expect(X("x1")).toEqual({ ...before, amount: 300000 });
    expect(removed).toEqual([]);
    expect(mem.activityLogs[0].details).toContain("250.000 → 300.000");
  });
  it("Thành viên sửa giao dịch do Admin ghi (endpoint gốc không chặn theo người tạo); người tạo giữ nguyên", () => {
    apply([{ type: "finance.update", txId: "x_admin", base: FP("x_admin"), changes: { category: "cc_pet", date: "2026-10-01", description: "Mèo", account: "bank" } }], MEMBER);
    expect(X("x_admin")).toMatchObject({ category: "cc_pet", date: "2026-10-01", description: "Mèo", account: "bank", creatorId: "u_admin", amount: 250000 });
  });
  it("khoản thu đổi nguồn thu (chữ tự do); khoản chi đổi sang hạng mục không còn → 422", () => {
    expect(apply([{ type: "finance.update", txId: "x_income", base: FP("x_income"), changes: { category: "Tiền thưởng" } }], ADMIN).r.status).toBe(200);
    expect(apply([{ type: "finance.update", txId: "x1", base: FP("x1"), changes: { category: "funeral" } }], ADMIN).r).toMatchObject({ status: 422, code: "invalid" });
  });
  it("fingerprint lệch (ai đó vừa sửa) / giao dịch đã xoá → 409, không ghi", () => {
    const stale = FP("x1");
    mem.transactions[0].amount = 260000;
    expect(apply([{ type: "finance.update", txId: "x1", base: stale, changes: { amount: 1 } }], ADMIN).r).toMatchObject({ status: 409, code: "conflict" });
    expect(apply([{ type: "finance.delete", txId: "x_nope", base: stale }], ADMIN).r).toMatchObject({ status: 409, code: "conflict" });
    expect(writes).toBe(0);
  });
  it("giao dịch cũ số tiền lẻ (fingerprint không tính được) → 422 hướng dẫn sửa trong app, không làm tròn", () => {
    const { r } = apply([{ type: "finance.update", txId: "x_frac", base: { fingerprint: "a".repeat(64) }, changes: { amount: 40000 } }], ADMIN);
    expect(r).toMatchObject({ status: 422, code: "invalid" });
    expect(r.ok === false && r.error).toContain("Thu chi");
    expect(X("x_frac").amount).toBe(35000.5);
  });
  it("nội dung rỗng (hợp đồng cho phép \"\") → 422 như form của app (review L2)", () => {
    expect(apply([{ type: "finance.update", txId: "x1", base: FP("x1"), changes: { description: "  " } }], ADMIN).r).toMatchObject({ status: 422, code: "invalid" });
    expect(apply([{ type: "finance.create", txType: "expense", amount: 1000, category: "food", date: "2026-10-10", description: "" }], ADMIN).r).toMatchObject({ status: 422, code: "invalid" });
    expect(writes).toBe(0);
  });
  it("ngày mới không có thật → 422; Con → 403", () => {
    expect(apply([{ type: "finance.update", txId: "x1", base: FP("x1"), changes: { date: "2026-13-01" } }], ADMIN).r.status).toBe(422);
    expect(apply([{ type: "finance.update", txId: "x1", base: FP("x1"), changes: { amount: 1 } }], KID).r).toMatchObject({ status: 403, code: "forbidden" });
  });
});

describe("finance.delete", () => {
  it("xoá giao dịch + nhật ký; file hoá đơn xoá SAU khi ghi", () => {
    const { r } = apply([{ type: "finance.delete", txId: "x1", base: FP("x1") }], MEMBER);
    expect(r.status).toBe(200);
    expect(mem.transactions.some((t) => t.id === "x1")).toBe(false);
    expect(removed).toEqual(["/uploads/receipts/x1.jpg"]);
    expect(mem.activityLogs[0].action).toBe("Xóa giao dịch tài chính");
  });
  it("xoá file lỗi ở một file không chặn các file còn lại (review L1)", () => {
    mem.transactions.push(tx("x2"));
    const seen: string[][] = [];
    deps.removeFiles = (urls) => { seen.push(urls); if (urls.includes("/uploads/receipts/x1.jpg")) throw new Error("EBUSY"); };
    const { r } = apply([{ type: "finance.delete", txId: "x1", base: FP("x1") }, { type: "finance.delete", txId: "x2", base: FP("x2") }], MEMBER);
    expect(r.status).toBe(200);
    expect(seen).toEqual([["/uploads/receipts/x1.jpg"], ["/uploads/receipts/x2.jpg"]]);
  });
  it("ghi lỗi → không xoá file hoá đơn", () => {
    deps.applyBatch = () => { throw new Error("SQLITE_IOERR"); };
    const { r } = apply([{ type: "finance.delete", txId: "x1", base: FP("x1") }], MEMBER);
    expect(r).toMatchObject({ status: 500, code: "write_failed" });
    expect(removed).toEqual([]);
  });
  it("Khách → 403; một lỗi trong đề xuất trộn 2 module → không ghi gì", () => {
    expect(apply([{ type: "finance.delete", txId: "x1", base: FP("x1") }], GUEST).r.status).toBe(403);
    const { r } = apply([
      { type: "shopping.add", items: [{ name: "Trứng" }] },
      { type: "finance.delete", txId: "x_frac", base: { fingerprint: "a".repeat(64) } },
    ], ADMIN);
    expect(r.status).toBe(422);
    expect(writes).toBe(0);
    expect(removed).toEqual([]);
  });
});
