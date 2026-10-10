/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Áp dụng một đề xuất của trợ lý sau khi người dùng bấm "Duyệt" (spec §9).
// Toàn bộ hàm ĐỒNG BỘ (không await): kiểm chủ sở hữu/hash/trạng thái/hạn → pending→applying có điều kiện
// → trong MỘT FamilyDB.applyBatch: kiểm guard + quyền trên chính bản DB đó rồi ghi tất cả → applied/failed.
// Người thao tác là người duyệt, không phải agent.

import { fingerprint, planHash, type AgentOperation, type AgentOperationType } from "./agentContract.js";
import type { AgentStore, ApplyResult, Proposal } from "./agentStore.js";
import {
  mutateAddShopping, mutateDeleteShopping, mutateSetShoppingPurchased,
  mutateCreateTask, mutateUpdateTask, mutateDeleteTask,
  mutateCreatePlan, mutateUpdatePlan, mutateDeletePlan,
  mutateCreateTransaction, mutateUpdateTransaction, mutateDeleteTransaction,
} from "./dataMutations.js";
import {
  canCreateTask, canEditTask, canDeleteTask, canCreatePlan, canEditPlan, canDeletePlan, canWriteFinance, sanitizeTaskWrite,
} from "./permissions.js";
import { BUILTIN_EXPENSE_CATEGORY_KEYS } from "../src/utils/builtinExpenseCategories.js";
import { isLimitedViewer, TransactionType } from "../src/types.js";
import type {
  FamilyOrganizerDB, FamilyPlan, FinancialTransaction, Notification, ShoppingItem, Task, UserRole,
} from "../src/types.js";

export interface ApplySession {
  userId: string;
  username: string;
  role: UserRole;
}

export interface ApplyDeps {
  store: AgentStore;
  applyBatch: <T>(fn: (db: FamilyOrganizerDB) => T) => T;
  /** Gọi SAU khi family.db đã ghi xong: gửi push cho các thông báo vừa tạo (ghi lỗi thì không gọi). */
  afterCommit?: (notifications: Notification[]) => void;
  /** Gọi SAU khi family.db đã ghi xong: xoá file (ảnh hoá đơn của giao dịch vừa xoá). Ghi lỗi thì không gọi. */
  removeFiles?: (urls: string[]) => void;
  now?: () => number;
}

export type ApplyCode =
  | "not_found" | "hash_mismatch" | "expired" | "applying" | "cancelled" | "failed"
  | "conflict" | "forbidden" | "invalid" | "unsupported" | "write_failed";

export type ApplyOutcome =
  | { ok: true; status: 200; proposal: Proposal; modules: string[] }
  | { ok: false; status: FailStatus; code: ApplyCode; error: string; proposal?: Proposal };

type FailStatus = 403 | 404 | 409 | 422 | 500 | 501;

/** Loại operation đã bật ghi. M1: đi chợ; M2: việc + lịch; M3: thu chi (đủ 12 loại của hợp đồng). */
export const ENABLED_OPERATIONS: ReadonlySet<AgentOperationType> = new Set([
  "shopping.add", "shopping.set_purchased", "shopping.delete",
  "task.create", "task.update", "task.delete",
  "plan.create", "plan.update", "plan.delete",
  "finance.create", "finance.update", "finance.delete",
]);

const CONFLICT_MSG = "Dữ liệu đã thay đổi kể từ lúc trợ lý đề xuất — hãy hỏi lại trợ lý.";

const fail = (
  status: FailStatus, code: ApplyCode, error: string, proposal?: Proposal,
): ApplyOutcome => ({ ok: false, status, code, error, proposal });

type Problem = { code: ApplyCode; error: string };

/** Chỉ mục dữ liệu hiện tại (lấy từ chính bản DB của batch) để kiểm guard/quyền. */
interface Snapshot {
  shopping: Map<string, ShoppingItem>;
  tasks: Map<string, Task>;
  plans: Map<string, FamilyPlan>;
  transactions: Map<string, FinancialTransaction>;
  activeUserIds: Set<string>;
  /** Hạng mục CHI đang dùng: mặc định chưa ẩn + hạng mục gia đình tự thêm (id cc_…). */
  expenseCategories: Set<string>;
}

function snapshotOf(db: FamilyOrganizerDB): Snapshot {
  return {
    shopping: new Map(db.shoppingItems.map((i) => [i.id, i])),
    tasks: new Map(db.tasks.map((t) => [t.id, t])),
    plans: new Map(db.plans.map((x) => [x.id, x])),
    transactions: new Map((db.transactions ?? []).map((x) => [x.id, x])),
    activeUserIds: new Set(db.users.filter((u) => !u.isDeleted).map((u) => u.id)),
    expenseCategories: new Set([
      ...BUILTIN_EXPENSE_CATEGORY_KEYS.filter((k) => !(db.hiddenBuiltinCategories ?? []).includes(k)),
      ...(db.customCategories ?? []).map((c) => c.id),
    ]),
  };
}

/** Một operation không qua được guard/quyền — ném trong batch để không ghi gì. */
class RejectedOperation extends Error {
  constructor(readonly problem: Problem) {
    super(problem.error);
  }
}

const FORBIDDEN_TASK = "Bạn không có quyền thay đổi công việc này.";
const FORBIDDEN_FINANCE = "Chỉ Admin/Thành viên được ghi, sửa hoặc xoá thu chi.";
const FORBIDDEN_PLAN = "Bạn chỉ thay đổi được sự kiện do mình tạo (Admin có toàn quyền); Khách không thêm/sửa lịch.";

const conflict: Problem = { code: "conflict", error: CONFLICT_MSG };
const forbidden = (error: string): Problem => ({ code: "forbidden", error });
const invalid = (error: string): Problem => ({ code: "invalid", error });

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}):(\d{2}))?$/;

/** "YYYY-MM-DD[ HH:mm]" là ngày/giờ có thật (hợp đồng chỉ kiểm định dạng). */
export function isRealDate(value: string): boolean {
  const m = DATE_RE.exec(value);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return false;
  return m[4] === undefined || (Number(m[4]) < 24 && Number(m[5]) < 60);
}

function checkAssignee(id: string | null | undefined, snap: Snapshot): Problem | null {
  if (id === undefined || id === null) return null;
  return snap.activeUserIds.has(id) ? null : invalid("Người được giao không có trong gia đình.");
}

function checkDue(due: string | undefined): Problem | null {
  return due === undefined || isRealDate(due) ? null : invalid(`Hạn "${due}" không phải ngày có thật.`);
}

/** Ngày + thứ lặp của sự kiện SAU khi gộp thay đổi. endDate rỗng chỉ hợp lệ với lịch lặp (lặp vô hạn). */
function checkPlanShape(p: Pick<FamilyPlan, "startDate" | "endDate" | "recurrenceType" | "recurrenceWeekdays">): Problem | null {
  if (!isRealDate(p.startDate)) return invalid(`Thời gian bắt đầu "${p.startDate}" không có thật.`);
  const recurring = !!p.recurrenceType && p.recurrenceType !== "none";
  if (p.endDate === "" && recurring) {
    // lặp vô hạn
  } else if (!isRealDate(p.endDate)) {
    return invalid(`Thời gian kết thúc "${p.endDate}" không có thật.`);
  } else if (p.endDate < p.startDate) {
    return invalid("Thời gian kết thúc phải sau hoặc bằng thời gian bắt đầu.");
  }
  if (p.recurrenceWeekdays && p.recurrenceWeekdays.length > 0 && p.recurrenceType !== "weekly") {
    return invalid("Chỉ sự kiện lặp hằng tuần mới chọn thứ lặp.");
  }
  return null;
}

/** Thay đổi sự kiện từ hợp đồng → trường lưu: isRecurring theo recurrenceType; bỏ thứ lặp khi không còn lặp tuần. */
function planChanges(changes: Extract<AgentOperation, { type: "plan.update" }>["changes"]): Partial<FamilyPlan> {
  const out: Partial<FamilyPlan> = { ...changes };
  if (changes.recurrenceType !== undefined) {
    out.isRecurring = changes.recurrenceType !== "none";
    if (changes.recurrenceType !== "weekly" && changes.recurrenceWeekdays === undefined) out.recurrenceWeekdays = undefined;
  }
  return out;
}

/** Giao dịch hiện tại khớp fingerprint lúc đề xuất? Số tiền lẻ (bản ghi cũ) → không tính được → báo sửa trong app. */
function checkTransactionBase(cur: FinancialTransaction | undefined, base: { fingerprint: string }): Problem | null {
  if (!cur) return conflict;
  let fp: string;
  try {
    fp = fingerprint("transaction", cur);
  } catch {
    return invalid(`Giao dịch "${cur.description}" có số tiền lẻ/dữ liệu lạ — hãy sửa trực tiếp trong mục Thu chi.`);
  }
  return fp === base.fingerprint ? null : conflict;
}

/** Hạng mục hợp lệ theo loại giao dịch: khoản chi phải là hạng mục đang dùng; khoản thu là chữ tự do (như app). */
function checkCategory(type: string, category: string | undefined, snap: Snapshot): Problem | null {
  if (category === undefined || type === TransactionType.INCOME) return null;
  return snap.expenseCategories.has(category)
    ? null
    : invalid(`Hạng mục chi "${category}" không còn dùng — hãy hỏi lại trợ lý hoặc chọn trong mục Thu chi.`);
}

/** Nội dung bắt buộc như form của app (hợp đồng cho phép chuỗi rỗng). */
function checkTxDescription(description: string | undefined): Problem | null {
  return description === undefined || description.trim() ? null : invalid("Nội dung giao dịch không được để trống.");
}

function checkTxDate(date: string | undefined): Problem | null {
  return date === undefined || isRealDate(date) ? null : invalid(`Ngày "${date}" không có thật.`);
}

/** Guard + quyền cho một operation trên dữ liệu hiện tại. Trả lý do lỗi hoặc null. */
function checkOperation(op: AgentOperation, snap: Snapshot, s: ApplySession): Problem | null {
  switch (op.type) {
    case "shopping.add":
      // Đi chợ: mọi vai trò đã đăng nhập được thêm/sửa/xoá mọi món (giống POST/DELETE /api/shopping).
      return null;
    case "shopping.set_purchased":
    case "shopping.delete": {
      const cur = snap.shopping.get(op.itemId);
      return !cur || cur.updatedAt !== op.base.updatedAt ? conflict : null;
    }

    case "task.create": {
      if (!canCreateTask(s)) return forbidden(FORBIDDEN_TASK);
      // Endpoint gốc lặng lẽ bỏ điểm của Con/Khách; ở đây từ chối để thẻ Duyệt không hiển thị sai.
      if (isLimitedViewer(s.role) && op.rewardPoints !== undefined) return forbidden("Con/Khách không tự đặt điểm thưởng.");
      return checkAssignee(op.assigneeId, snap) ?? checkDue(op.dueDate);
    }
    case "task.update": {
      const cur = snap.tasks.get(op.taskId);
      if (!cur || cur.updatedAt !== op.base.updatedAt) return conflict;
      if (!canEditTask(cur, s)) return forbidden(FORBIDDEN_TASK);
      // Cùng luật làm sạch với POST /api/tasks: trường nào bị bỏ (Con chỉ được giao → chỉ đổi trạng thái) = không được phép.
      const cleaned = sanitizeTaskWrite({ ...op.changes }, cur, s);
      if (!cleaned.ok || Object.keys(op.changes).some((k) => !(k in cleaned.data))) {
        return forbidden("Với việc được giao, bạn chỉ đổi được trạng thái.");
      }
      if (cur.pendingApproval) return forbidden("Việc đang chờ duyệt — hãy duyệt hoặc trả lại trong mục Việc.");
      if (op.changes.status !== undefined && cur.status === "completed") {
        return forbidden("Việc đã hoàn thành — muốn mở lại hãy làm trong mục Việc.");
      }
      return checkAssignee(op.changes.assigneeId, snap) ?? checkDue(op.changes.dueDate);
    }
    case "task.delete": {
      const cur = snap.tasks.get(op.taskId);
      if (!cur || cur.updatedAt !== op.base.updatedAt) return conflict;
      return canDeleteTask(s) ? null : forbidden("Chỉ Admin/Thành viên được xoá công việc.");
    }

    case "plan.create": {
      if (!canCreatePlan(s)) return forbidden(FORBIDDEN_PLAN);
      return checkPlanShape({
        startDate: op.startDate, endDate: op.endDate,
        recurrenceType: op.recurrenceType ?? "none", recurrenceWeekdays: op.recurrenceWeekdays,
      });
    }
    case "plan.update": {
      const cur = snap.plans.get(op.planId);
      if (!cur || fingerprint("plan", cur) !== op.base.fingerprint) return conflict;
      if (!canEditPlan(cur, s)) return forbidden(FORBIDDEN_PLAN);
      return checkPlanShape({ ...cur, ...planChanges(op.changes) });
    }
    case "plan.delete": {
      const cur = snap.plans.get(op.planId);
      if (!cur || fingerprint("plan", cur) !== op.base.fingerprint) return conflict;
      return canDeletePlan(cur, s) ? null : forbidden(FORBIDDEN_PLAN);
    }

    // Thu chi: như POST/DELETE /api/finance — Admin/Thành viên sửa/xoá được mọi giao dịch.
    case "finance.create":
      if (!canWriteFinance(s)) return forbidden(FORBIDDEN_FINANCE);
      return checkTxDescription(op.description) ?? checkTxDate(op.date) ?? checkCategory(op.txType, op.category, snap);
    case "finance.update": {
      if (!canWriteFinance(s)) return forbidden(FORBIDDEN_FINANCE);
      const cur = snap.transactions.get(op.txId);
      return checkTransactionBase(cur, op.base)
        ?? checkTxDescription(op.changes.description)
        ?? checkTxDate(op.changes.date)
        ?? checkCategory(cur!.type, op.changes.category, snap);
    }
    case "finance.delete":
      if (!canWriteFinance(s)) return forbidden(FORBIDDEN_FINANCE);
      return checkTransactionBase(snap.transactions.get(op.txId), op.base);

    default:
      return { code: "unsupported", error: "Trợ lý chưa hỗ trợ thay đổi loại dữ liệu này." };
  }
}

/** Bản ghi mà operation sửa/xoá (để chặn một bản ghi bị đụng hai lần trong cùng đề xuất). */
function targetOf(op: AgentOperation): string | null {
  if ("itemId" in op) return `shopping:${op.itemId}`;
  if ("taskId" in op) return `task:${op.taskId}`;
  if ("planId" in op) return `plan:${op.planId}`;
  if ("txId" in op) return `finance:${op.txId}`;
  return null;
}

/** Việc cần làm SAU khi ghi xong (ghi lỗi thì bỏ cả). */
interface AfterCommit {
  notices: Notification[];
  files: string[];
}

function runOperation(db: FamilyOrganizerDB, op: AgentOperation, index: number, s: ApplySession, after: AfterCommit): ApplyResult {
  const { notices } = after;
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
    case "task.create": {
      const { type: _t, ...data } = op;
      return { index, ok: true, id: mutateCreateTask(db, data as Partial<Task>, s.userId, s.username, notices).id };
    }
    case "task.update":
      return { index, ok: true, id: mutateUpdateTask(db, op.taskId, op.changes, s.userId, s.username).id };
    case "task.delete": {
      const removed = mutateDeleteTask(db, op.taskId, s.userId, s.username);
      return removed ? { index, ok: true, id: removed.id } : { index, ok: true, id: op.taskId, skipped: true };
    }
    case "plan.create": {
      const { type: _t, ...data } = op;
      const recurrenceType = data.recurrenceType ?? "none";
      const plan = mutateCreatePlan(db, { ...data, recurrenceType, isRecurring: recurrenceType !== "none" }, s.userId, s.username, notices);
      return { index, ok: true, id: plan.id };
    }
    case "plan.update": {
      return { index, ok: true, id: mutateUpdatePlan(db, op.planId, planChanges(op.changes), s.userId, s.username).id };
    }
    case "plan.delete": {
      const removed = mutateDeletePlan(db, op.planId, s.userId, s.username);
      return removed ? { index, ok: true, id: removed.id } : { index, ok: true, id: op.planId, skipped: true };
    }
    case "finance.create": {
      const { type: _t, txType, ...data } = op;
      return { index, ok: true, id: mutateCreateTransaction(db, { ...data, type: txType as TransactionType } as Partial<FinancialTransaction>, s.userId, s.username).id };
    }
    case "finance.update":
      return { index, ok: true, id: mutateUpdateTransaction(db, op.txId, op.changes, s.userId, s.username).id };
    case "finance.delete": {
      const removed = mutateDeleteTransaction(db, op.txId, s.userId, s.username);
      if (removed?.receiptImage) after.files.push(removed.receiptImage);
      return removed ? { index, ok: true, id: removed.id } : { index, ok: true, id: op.txId, skipped: true };
    }
    default:
      // checkOperation đã chặn trước — tới đây là lỗi lập trình.
      throw new Error(`operation chưa hỗ trợ: ${(op as { type: string }).type}`);
  }
}

const STATUS_OF: Partial<Record<ApplyCode, FailStatus>> = { forbidden: 403, invalid: 422, unsupported: 501 };

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
  const modules = new Set(p.operations.map((op) => op.type.split(".")[0]));
  const targets = p.operations.map(targetOf).filter((t): t is string => t !== null);
  if (new Set(targets).size !== targets.length) {
    const error = "Đề xuất thay đổi một bản ghi nhiều lần — hãy hỏi lại trợ lý.";
    store.markPending(p.id, "failed", error);
    return fail(422, "invalid", error, store.getProposal(p.id));
  }

  if (!store.beginApply(p.id)) {
    const cur = store.getProposal(p.id);
    if (cur?.status === "applied") return { ok: true, status: 200, proposal: cur, modules: [] };
    return fail(409, "applying", "Đề xuất đang được áp dụng.", cur);
  }

  // Kiểm guard + quyền NGAY TRÊN bản DB của batch (một lần đọc, không có khe giữa kiểm và ghi):
  // có lỗi thì ném RejectedOperation → applyBatch không ghi gì.
  let results: ApplyResult[];
  const after: AfterCommit = { notices: [], files: [] };
  try {
    results = deps.applyBatch((db) => {
      const snap = snapshotOf(db);
      for (const op of p.operations) {
        const problem = checkOperation(op, snap, session);
        if (problem) throw new RejectedOperation(problem);
      }
      return p.operations.map((op, i) => runOperation(db, op, i, session, after));
    });
  } catch (e) {
    if (e instanceof RejectedOperation) {
      store.finishApply(p.id, "failed", [], now, e.problem.error);
      return fail(STATUS_OF[e.problem.code] ?? 409, e.problem.code, e.problem.error, store.getProposal(p.id));
    }
    console.error("Lỗi áp dụng đề xuất trợ lý:", (e as Error)?.message);
    const error = "Không lưu được thay đổi — chưa có gì bị ghi. Hãy thử lại.";
    store.finishApply(p.id, "failed", [], now, error);
    return fail(500, "write_failed", error, store.getProposal(p.id));
  }
  try {
    if (after.notices.length > 0) deps.afterCommit?.(after.notices);
  } catch (e) {
    console.error("Không gửi được thông báo sau khi áp dụng đề xuất:", (e as Error)?.message);
  }
  for (const url of after.files) {
    try {
      deps.removeFiles?.([url]); // từng file: một file lỗi không chặn các file còn lại
    } catch (e) {
      console.error("Không xoá được file sau khi áp dụng đề xuất:", (e as Error)?.message);
    }
  }
  const events = [...modules].map((m) => MODULE_EVENT[m]);
  // family.db đã ghi xong: lỗi ở agent.db KHÔNG được biến thành "thất bại" (dữ liệu đã có) —
  // vẫn trả thành công để broadcast; proposal kẹt `applying` sẽ thành `failed` ở lần khởi động sau.
  try {
    store.finishApply(p.id, "applied", results, now);
    return { ok: true, status: 200, proposal: store.getProposal(p.id)!, modules: events };
  } catch (e) {
    console.error("Đã áp dụng đề xuất nhưng không cập nhật được agent.db:", (e as Error)?.message);
    return { ok: true, status: 200, proposal: { ...p, status: "applied", results, appliedAt: new Date(now).toISOString() }, modules: events };
  }
}
