/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";
import { AgentStore } from "./agentStore.js";
import { applyProposal, type ApplyDeps } from "./agentApply.js";
import { planHash, type AgentOperation } from "./agentContract.js";
import type { FamilyOrganizerDB, ShoppingItem } from "../src/types.js";
import { UserRole } from "../src/types.js";

const T0 = Date.parse("2026-10-10T10:00:00.000Z");
const me = { userId: "u1", username: "me", role: UserRole.CHILD };

let dir: string;
let store: AgentStore;
// Dạng DB đã normalize (applyBatch luôn đưa bản đầy đủ) — chỉ các mảng mà apply đọc tới.
let mem: Pick<FamilyOrganizerDB, "shoppingItems" | "activityLogs" | "tasks" | "plans" | "users" | "notifications">;
let clock: { t: number };
let failWrite: boolean;
let writes: number;
let deps: ApplyDeps;

function item(id: string, extra: Partial<ShoppingItem> = {}): ShoppingItem {
  return {
    id, name: id, isPurchased: false, creatorId: "admin", purchasedById: null,
    createdAt: "2026-10-01T00:00:00.000Z", updatedAt: "2026-10-01T00:00:00.000Z", ...extra,
  };
}

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "fo-agent-apply-"));
  store = new AgentStore(path.join(dir, "agent.db"));
  mem = { shoppingItems: [item("s1"), item("s2", { isPurchased: true, purchasedById: "admin" })], activityLogs: [], tasks: [], plans: [], users: [], notifications: [] };
  clock = { t: T0 };
  failWrite = false;
  writes = 0;
  deps = {
    store,
    now: () => clock.t,
    applyBatch: (fn) => {
      const copy = structuredClone(mem) as FamilyOrganizerDB;
      const r = fn(copy);
      if (failWrite) throw new Error("SQLITE_FULL");
      mem = copy;
      writes++;
      return r;
    },
  };
});
afterEach(() => {
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

function propose(ops: AgentOperation[], userId = "u1") {
  return store.createProposal({ conversationId: "c1", userId, operations: ops, planHash: planHash(ops), preview: [] }, clock.t);
}
const B = (updatedAt = "2026-10-01T00:00:00.000Z") => ({ updatedAt });

describe("applyProposal", () => {
  it("áp dụng add + set_purchased + delete trong một lần ghi; người thao tác = người duyệt", () => {
    const p = propose([
      { type: "shopping.add", items: [{ name: "sữa", quantity: "2 hộp" }, { name: "trứng" }] },
      { type: "shopping.set_purchased", itemId: "s1", purchased: true, base: B() },
      { type: "shopping.delete", itemId: "s2", base: B() },
    ]);
    const r = applyProposal(deps, p.id, p.planHash, me);
    expect(r.status).toBe(200);
    expect(writes).toBe(1);
    expect(mem.shoppingItems.map((i) => i.name).sort()).toEqual(["s1", "sữa", "trứng"]);
    expect(mem.shoppingItems.find((i) => i.name === "sữa")).toMatchObject({ creatorId: "u1", quantity: "2 hộp" });
    expect(mem.shoppingItems.find((i) => i.id === "s1")).toMatchObject({ isPurchased: true, purchasedById: "u1" });
    expect(r.ok && r.modules).toEqual(["SHOPPING_UPDATE"]);
    const saved = store.getProposal(p.id)!;
    expect(saved.status).toBe("applied");
    expect(saved.results?.[0]).toMatchObject({ index: 0, ok: true });
    expect(saved.results?.[0].ids).toHaveLength(2);
  });

  it("set_purchased bằng trạng thái hiện tại → bỏ qua, không lật", () => {
    const p = propose([{ type: "shopping.set_purchased", itemId: "s2", purchased: true, base: B() }]);
    const r = applyProposal(deps, p.id, p.planHash, me);
    expect(r.status).toBe(200);
    expect(mem.shoppingItems.find((i) => i.id === "s2")?.isPurchased).toBe(true);
    expect(store.getProposal(p.id)?.results?.[0]).toMatchObject({ ok: true, skipped: true });
  });

  it("planHash sai → 409, không ghi", () => {
    const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
    const r = applyProposal(deps, p.id, "0".repeat(64), me);
    expect(r).toMatchObject({ status: 409, code: "hash_mismatch" });
    expect(writes).toBe(0);
    expect(store.getProposal(p.id)?.status).toBe("pending");
  });

  it("hết hạn → 409 expired, đánh dấu expired", () => {
    const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
    clock.t += 31 * 60 * 1000;
    expect(applyProposal(deps, p.id, p.planHash, me)).toMatchObject({ status: 409, code: "expired" });
    expect(store.getProposal(p.id)?.status).toBe("expired");
    expect(writes).toBe(0);
  });

  it("người khác bấm (kể cả admin) → 404, không ghi", () => {
    const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
    const r = applyProposal(deps, p.id, p.planHash, { userId: "admin", username: "a", role: UserRole.ADMIN });
    expect(r.status).toBe(404);
    expect(writes).toBe(0);
    expect(store.getProposal(p.id)?.status).toBe("pending");
  });

  it("guard lệch (món vừa bị sửa) → 409 conflict, failed, không ghi gì kể cả op hợp lệ", () => {
    const p = propose([
      { type: "shopping.add", items: [{ name: "x" }] },
      { type: "shopping.delete", itemId: "s1", base: B("2026-09-01T00:00:00.000Z") },
    ]);
    const r = applyProposal(deps, p.id, p.planHash, me);
    expect(r).toMatchObject({ status: 409, code: "conflict" });
    expect(writes).toBe(0);
    expect(mem.shoppingItems).toHaveLength(2);
    expect(store.getProposal(p.id)?.status).toBe("failed");
  });

  it("món không còn tồn tại → 409 conflict", () => {
    const p = propose([{ type: "shopping.set_purchased", itemId: "gone", purchased: true, base: B() }]);
    expect(applyProposal(deps, p.id, p.planHash, me)).toMatchObject({ status: 409, code: "conflict" });
  });

  it("idempotent: bấm lại khi đã applied → trả kết quả cũ, không ghi lần hai", () => {
    const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
    const a = applyProposal(deps, p.id, p.planHash, me);
    const b = applyProposal(deps, p.id, p.planHash, me);
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(b.ok && b.modules).toEqual([]);
    expect(writes).toBe(1);
    expect(mem.shoppingItems).toHaveLength(3);
  });

  it("đang applying (lượt khác giữ) → 409", () => {
    const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
    store.beginApply(p.id);
    expect(applyProposal(deps, p.id, p.planHash, me)).toMatchObject({ status: 409, code: "applying" });
    expect(writes).toBe(0);
  });

  it("đã huỷ → 409", () => {
    const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
    store.cancel(p.id, "u1");
    expect(applyProposal(deps, p.id, p.planHash, me)).toMatchObject({ status: 409, code: "cancelled" });
  });

  it("ghi lỗi → failed, không còn dòng nào", () => {
    failWrite = true;
    const p = propose([{ type: "shopping.add", items: Array.from({ length: 30 }, (_, i) => ({ name: `m${i}` })) }]);
    const r = applyProposal(deps, p.id, p.planHash, me);
    expect(r).toMatchObject({ status: 500, code: "write_failed" });
    expect(mem.shoppingItems).toHaveLength(2);
    expect(store.getProposal(p.id)?.status).toBe("failed");
  });

  it("30 món → đúng 30 dòng mới", () => {
    const p = propose([{ type: "shopping.add", items: Array.from({ length: 30 }, (_, i) => ({ name: `m${i}` })) }]);
    expect(applyProposal(deps, p.id, p.planHash, me).status).toBe(200);
    expect(mem.shoppingItems).toHaveLength(32);
  });

  it("operations trong DB bị sửa (hash lưu không khớp nội dung) → 409", () => {
    const ops: AgentOperation[] = [{ type: "shopping.add", items: [{ name: "x" }] }];
    const p = store.createProposal({ conversationId: "c1", userId: "u1", operations: ops, planHash: "f".repeat(64), preview: [] }, T0);
    expect(applyProposal(deps, p.id, "f".repeat(64), me)).toMatchObject({ status: 409, code: "hash_mismatch" });
  });
});

it("M2: ghi family.db xong mà cập nhật agent.db lỗi → vẫn báo thành công + broadcast", () => {
  const p = propose([{ type: "shopping.add", items: [{ name: "x" }] }]);
  const orig = store.finishApply.bind(store);
  store.finishApply = () => { throw new Error("SQLITE_IOERR"); };
  const r = applyProposal(deps, p.id, p.planHash, me);
  store.finishApply = orig;
  expect(r.status).toBe(200);
  expect(r.ok && r.modules).toEqual(["SHOPPING_UPDATE"]);
  expect(mem.shoppingItems).toHaveLength(3);
});
