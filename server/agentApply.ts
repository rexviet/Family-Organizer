/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Áp dụng một đề xuất của trợ lý sau khi người dùng bấm "Duyệt" (spec §9).
// Toàn bộ hàm ĐỒNG BỘ (không await): kiểm chủ sở hữu/hash/trạng thái/hạn → dry-run guard + quyền
// → pending→applying có điều kiện → ghi tất cả trong MỘT FamilyDB.applyBatch → applied/failed.
// Người thao tác là người duyệt, không phải agent.

import { planHash, type AgentOperation, type AgentOperationType } from "./agentContract.js";
import type { AgentStore, ApplyResult, Proposal } from "./agentStore.js";
import { mutateAddShopping, mutateDeleteShopping, mutateSetShoppingPurchased } from "./dataMutations.js";
import type { FamilyOrganizerDB, ShoppingItem, UserRole } from "../src/types.js";

export interface ApplySession {
  userId: string;
  username: string;
  role: UserRole;
}

export interface ApplyDeps {
  store: AgentStore;
  applyBatch: <T>(fn: (db: FamilyOrganizerDB) => T) => T;
  getShoppingItems: () => ShoppingItem[];
  now?: () => number;
}

export type ApplyCode =
  | "not_found" | "hash_mismatch" | "expired" | "applying" | "cancelled" | "failed"
  | "conflict" | "forbidden" | "unsupported" | "write_failed";

export type ApplyOutcome =
  | { ok: true; status: 200; proposal: Proposal; modules: string[] }
  | { ok: false; status: 403 | 404 | 409 | 500 | 501; code: ApplyCode; error: string; proposal?: Proposal };

/** Loại operation đã bật ghi. M2 thêm task/plan, M3 thêm finance. */
export const ENABLED_OPERATIONS: ReadonlySet<AgentOperationType> = new Set([
  "shopping.add", "shopping.set_purchased", "shopping.delete",
]);

const CONFLICT_MSG = "Dữ liệu đã thay đổi kể từ lúc trợ lý đề xuất — hãy hỏi lại trợ lý.";

const fail = (
  status: 403 | 404 | 409 | 500 | 501, code: ApplyCode, error: string, proposal?: Proposal,
): ApplyOutcome => ({ ok: false, status, code, error, proposal });

/** Guard + quyền cho một operation trên dữ liệu hiện tại. Trả lý do lỗi hoặc null. */
function checkOperation(op: AgentOperation, shopping: Map<string, ShoppingItem>): { code: ApplyCode; error: string } | null {
  switch (op.type) {
    case "shopping.add":
      // Đi chợ: mọi vai trò đã đăng nhập được thêm/sửa/xoá mọi món (giống POST/DELETE /api/shopping).
      return null;
    case "shopping.set_purchased":
    case "shopping.delete": {
      const cur = shopping.get(op.itemId);
      if (!cur || cur.updatedAt !== op.base.updatedAt) return { code: "conflict", error: CONFLICT_MSG };
      return null;
    }
    default:
      return { code: "unsupported", error: "Trợ lý chưa hỗ trợ thay đổi loại dữ liệu này." };
  }
}

function runOperation(db: FamilyOrganizerDB, op: AgentOperation, index: number, s: ApplySession): ApplyResult {
  switch (op.type) {
    case "shopping.add": {
      const ids = op.items.map((it) => mutateAddShopping(db, it, s.userId, s.username).id);
      return { index, ok: true, ids };
    }
    case "shopping.set_purchased": {
      const { item, changed } = mutateSetShoppingPurchased(db, op.itemId, op.purchased, s.userId);
      return changed ? { index, ok: true, id: item.id } : { index, ok: true, id: item.id, skipped: true };
    }
    case "shopping.delete": {
      const removed = mutateDeleteShopping(db, op.itemId, s.userId, s.username);
      return removed ? { index, ok: true, id: removed.id } : { index, ok: true, id: op.itemId, skipped: true };
    }
    default:
      // checkOperation đã chặn trước — tới đây là lỗi lập trình.
      throw new Error(`operation chưa hỗ trợ: ${op.type}`);
  }
}

const MODULE_EVENT: Record<string, string> = { shopping: "SHOPPING_UPDATE", task: "TASKS_UPDATE", plan: "PLANS_UPDATE", finance: "FINANCE_UPDATE" };

export function applyProposal(deps: ApplyDeps, proposalId: string, hash: unknown, session: ApplySession): ApplyOutcome {
  const now = (deps.now ?? Date.now)();
  const { store } = deps;

  const p = store.getProposal(proposalId);
  // Của người khác = không tồn tại với người này (không ai apply hộ, kể cả admin).
  if (!p || p.userId !== session.userId) return fail(404, "not_found", "Không tìm thấy đề xuất.");
  if (typeof hash !== "string" || hash !== p.planHash || planHash(p.operations) !== p.planHash) {
    return fail(409, "hash_mismatch", "Đề xuất không khớp với nội dung đã hiển thị — hãy tải lại.", p);
  }
  if (p.status === "applied") return { ok: true, status: 200, proposal: p, modules: [] };
  if (p.status !== "pending") {
    const msg: Record<string, string> = {
      applying: "Đề xuất đang được áp dụng.",
      cancelled: "Đề xuất đã bị huỷ.",
      expired: "Đề xuất đã hết hạn — hãy hỏi lại trợ lý.",
      failed: p.error || "Đề xuất đã thất bại trước đó.",
    };
    return fail(409, p.status as ApplyCode, msg[p.status] ?? "Đề xuất không còn hiệu lực.", p);
  }
  if (now >= Date.parse(p.expiresAt)) {
    store.markPending(p.id, "expired");
    return fail(409, "expired", "Đề xuất đã hết hạn (30 phút) — hãy hỏi lại trợ lý.", store.getProposal(p.id));
  }

  // Dry-run: kiểm hết trước, có lỗi thì không ghi gì.
  if (p.operations.some((op) => !ENABLED_OPERATIONS.has(op.type))) {
    store.markPending(p.id, "failed", "Trợ lý chưa hỗ trợ thay đổi loại dữ liệu này.");
    return fail(501, "unsupported", "Trợ lý chưa hỗ trợ thay đổi loại dữ liệu này.", store.getProposal(p.id));
  }
  const shopping = new Map(deps.getShoppingItems().map((i) => [i.id, i]));
  for (const op of p.operations) {
    const problem = checkOperation(op, shopping);
    if (problem) {
      store.markPending(p.id, "failed", problem.error);
      const status = problem.code === "forbidden" ? 403 : problem.code === "unsupported" ? 501 : 409;
      return fail(status, problem.code, problem.error, store.getProposal(p.id));
    }
  }

  if (!store.beginApply(p.id)) {
    const cur = store.getProposal(p.id);
    if (cur?.status === "applied") return { ok: true, status: 200, proposal: cur, modules: [] };
    return fail(409, "applying", "Đề xuất đang được áp dụng.", cur);
  }

  let results: ApplyResult[];
  try {
    results = deps.applyBatch((db) => p.operations.map((op, i) => runOperation(db, op, i, session)));
  } catch (e) {
    console.error("Lỗi áp dụng đề xuất trợ lý:", (e as Error)?.message);
    const error = "Không lưu được thay đổi — chưa có gì bị ghi. Hãy thử lại.";
    store.finishApply(p.id, "failed", [], now, error);
    return fail(500, "write_failed", error, store.getProposal(p.id));
  }
  const modules = [...new Set(p.operations.map((op) => MODULE_EVENT[op.type.split(".")[0]]))];
  // family.db đã ghi xong: lỗi ở agent.db KHÔNG được biến thành "thất bại" (dữ liệu đã có) —
  // vẫn trả thành công để broadcast; proposal kẹt `applying` sẽ thành `failed` ở lần khởi động sau.
  try {
    store.finishApply(p.id, "applied", results, now);
    return { ok: true, status: 200, proposal: store.getProposal(p.id)!, modules };
  } catch (e) {
    console.error("Đã áp dụng đề xuất nhưng không cập nhật được agent.db:", (e as Error)?.message);
    return { ok: true, status: 200, proposal: { ...p, status: "applied", results, appliedAt: new Date(now).toISOString() }, modules };
  }
}
