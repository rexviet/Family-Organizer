/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Hàm sửa dữ liệu THUẦN: chỉ sửa trên một bản FamilyOrganizerDB đã đọc, không đọc/ghi SQLite.
// Dùng chung cho endpoint thường (FamilyDB.save*/delete*) và apply đề xuất của trợ lý
// (FamilyDB.applyBatch) để hai đường ghi không lệch nhau. File không có side effect khi import.

import crypto from "crypto";
import { AccountType, TransactionType } from "../src/types.js";
import type { FamilyOrganizerDB, FamilyPlan, FinancialTransaction, Notification, ShoppingItem, Task } from "../src/types.js";

/** ID mới: tiền tố + thời gian + hậu tố ngẫu nhiên — ghi nhiều bản ghi liền nhau không trùng. */
export function newId(prefix: string): string {
  return `${prefix}_${Date.now()}_${crypto.randomBytes(6).toString("hex")}`;
}

const MAX_ACTIVITY_LOGS = 300;
const MAX_NOTIFICATIONS = 200;

export function mutateLogActivity(db: FamilyOrganizerDB, userId: string, username: string, action: string, details: string): void {
  db.activityLogs.unshift({
    id: newId("log"),
    userId,
    username,
    action,
    details,
    createdAt: new Date().toISOString()
  });
  // Cap logs to keep it lightweight on Raspberry Pi 5
  if (db.activityLogs.length > MAX_ACTIVITY_LOGS) {
    db.activityLogs = db.activityLogs.slice(0, MAX_ACTIVITY_LOGS);
  }
}

/** Thêm một món đi chợ vào `db` (chưa ghi) + nhật ký. */
export function mutateAddShopping(
  db: FamilyOrganizerDB,
  data: Partial<ShoppingItem>,
  userId: string,
  username: string
): ShoppingItem {
  const now = new Date().toISOString();
  const newItem: ShoppingItem = {
    id: newId("shop"),
    name: (data.name || "Món đồ").trim(),
    quantity: data.quantity?.trim() || "",
    note: data.note?.trim() || "",
    cat: data.cat?.trim() || "",
    isPurchased: false,
    creatorId: userId,
    purchasedById: null,
    createdAt: now,
    updatedAt: now
  };
  db.shoppingItems.unshift(newItem);
  mutateLogActivity(db, userId, username, "Thêm đồ đi chợ", `Đã thêm "${newItem.name}" vào danh sách mua sắm.`);
  return newItem;
}

/** ĐẶT trạng thái đã mua (không lật). Bằng trạng thái hiện tại → không đổi gì, changed=false. */
export function mutateSetShoppingPurchased(
  db: FamilyOrganizerDB,
  id: string,
  purchased: boolean,
  userId: string
): { item: ShoppingItem; changed: boolean } {
  const item = db.shoppingItems.find(i => i.id === id);
  if (!item) throw new Error("Món đồ không tồn tại");
  if (Boolean(item.isPurchased) === purchased) return { item, changed: false };
  item.isPurchased = purchased;
  item.purchasedById = purchased ? userId : null;
  item.updatedAt = new Date().toISOString();
  return { item, changed: true };
}

/** Xoá một món + nhật ký. Không tồn tại → null (giống DELETE /api/shopping/:id). */
export function mutateDeleteShopping(
  db: FamilyOrganizerDB,
  id: string,
  userId: string,
  username: string
): ShoppingItem | null {
  const idx = db.shoppingItems.findIndex(i => i.id === id);
  if (idx === -1) return null;
  const [removed] = db.shoppingItems.splice(idx, 1);
  mutateLogActivity(db, userId, username, "Xóa đồ đi chợ", `Đã xóa "${removed.name}" khỏi danh sách mua sắm.`);
  return removed;
}


// ---------------------------------------------------------------------------
// Thông báo — chỉ ghi vào `db`; push hệ thống do người gọi gửi SAU khi ghi xong
// (ghi lỗi thì không ai nhận thông báo về thứ không tồn tại).
// ---------------------------------------------------------------------------

export function mutateAddNotification(
  db: FamilyOrganizerDB,
  userId: string,
  title: string,
  content: string,
  type: Notification["type"] = "system"
): Notification {
  const notif: Notification = {
    id: newId("notif"),
    userId,
    title,
    content,
    type,
    isRead: false,
    createdAt: new Date().toISOString()
  };
  db.notifications.unshift(notif);
  if (db.notifications.length > MAX_NOTIFICATIONS) {
    db.notifications = db.notifications.slice(0, MAX_NOTIFICATIONS);
  }
  return notif;
}

// ---------------------------------------------------------------------------
// Việc
// ---------------------------------------------------------------------------

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** Hạn chỉ có ngày → ghép giờ (giờ cũ của việc nếu có, không thì cuối ngày 23:59). */
export function withDueTime(due: string, previous?: string | null): string {
  if (!DATE_ONLY.test(due)) return due;
  const time = /^\d{4}-\d{2}-\d{2} (\d{2}:\d{2})/.exec(previous || "")?.[1] ?? "23:59";
  return `${due} ${time}`;
}

/** Tạo việc (giống nhánh tạo của POST /api/tasks) + nhật ký + thông báo (đẩy vào `notices`). */
export function mutateCreateTask(
  db: FamilyOrganizerDB,
  taskData: Partial<Task>,
  userId: string,
  username: string,
  notices: Notification[] = []
): Task {
  const nowStr = new Date().toISOString();
  const data = taskData as Partial<Task> & Record<string, unknown>;
  const newTask: Task = {
    id: newId("task"),
    title: taskData.title || "Công việc mới",
    description: taskData.description || "",
    status: taskData.status || ("todo" as Task["status"]),
    priority: taskData.priority || ("medium" as Task["priority"]),
    dueDate: taskData.dueDate
      ? withDueTime(taskData.dueDate)
      : new Date(Date.now() + 86400000).toISOString().slice(0, 10) + " 12:00",
    creatorId: userId,
    assigneeId: taskData.assigneeId || null,
    isShared: taskData.isShared !== undefined ? taskData.isShared : true,
    tags: taskData.tags || [],
    rewardPoints: Math.max(0, Number(data.rewardPoints || 0)),
    completedById: null,
    completedAt: null,
    recurrenceType: (data.recurrenceType as Task["recurrenceType"]) || "none",
    recurrenceInterval: Math.max(1, Number(data.recurrenceInterval || 1)),
    recurrenceEndDate: (data.recurrenceEndDate as string) || undefined,
    rotationMemberIds: (data.rotationMemberIds as string[]) || undefined,
    sourceRecurringTaskId: null,
    comments: [],
    history: [{
      id: newId("h"),
      userId,
      username,
      action: "Đã khởi tạo công việc này",
      createdAt: nowStr
    }],
    createdAt: nowStr,
    updatedAt: nowStr
  };

  db.tasks.push(newTask);
  mutateLogActivity(db, userId, username, "Tạo Task", `Đã lập công việc mới "${newTask.title}".`);

  if (newTask.assigneeId && newTask.assigneeId !== userId) {
    notices.push(mutateAddNotification(db, newTask.assigneeId, "Công việc mới được giao", `Bạn vừa được giao nhiệm vụ: "${newTask.title}"`));
  } else if (newTask.isShared) {
    notices.push(mutateAddNotification(db, "all", "Công việc gia đình mới", `Cả nhà ơi có nhiệm vụ: "${newTask.title}"`));
  }
  return newTask;
}

/** Các trường trợ lý được sửa trên một việc (khớp `task.update.changes` của hợp đồng). */
export interface TaskFieldChanges {
  title?: string;
  description?: string;
  dueDate?: string;
  assigneeId?: string | null;
  priority?: "low" | "medium" | "high";
  status?: "todo" | "in_progress";
}

/**
 * Sửa một số trường của việc: MERGE vào bản hiện tại (trường không nêu giữ nguyên), ghi lịch sử
 * đổi trạng thái/người được giao như POST /api/tasks. KHÔNG xử lý hoàn thành/cộng điểm/duyệt —
 * người gọi phải chặn trước (trợ lý không được hoàn thành/duyệt việc).
 */
export function mutateUpdateTask(
  db: FamilyOrganizerDB,
  id: string,
  changes: TaskFieldChanges,
  userId: string,
  username: string
): Task {
  const idx = db.tasks.findIndex(t => t.id === id);
  if (idx === -1) throw new Error("Task không tồn tại");
  const old = db.tasks[idx];
  const nowStr = new Date().toISOString();

  const changelog: string[] = [];
  if (changes.status && changes.status !== old.status) {
    changelog.push(`trạng thái từ '${old.status}' thành '${changes.status}'`);
  }
  if (changes.assigneeId !== undefined && changes.assigneeId !== old.assigneeId) {
    const u = db.users.find(x => x.id === changes.assigneeId);
    changelog.push(`giao việc cho ${u ? u.fullName : "Chưa phân công"}`);
  }
  const history = [...(old.history || [])];
  if (changelog.length > 0) {
    history.unshift({ id: newId("h"), userId, username, action: `Đã thay đổi: ${changelog.join(", ")}`, createdAt: nowStr });
  }

  const patch: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(changes)) {
    if (v !== undefined) patch[k] = v;
  }
  if (changes.dueDate) patch.dueDate = withDueTime(changes.dueDate, old.dueDate);

  const updated: Task = { ...old, ...patch, history, updatedAt: nowStr } as Task;
  db.tasks[idx] = updated;
  mutateLogActivity(db, userId, username, "Cập nhật Task", `Đã sửa đổi công việc "${updated.title}".`);
  return updated;
}

/** Xoá việc + nhật ký. Không tồn tại → null (giống DELETE /api/tasks/:id). */
export function mutateDeleteTask(db: FamilyOrganizerDB, id: string, userId: string, username: string): Task | null {
  const idx = db.tasks.findIndex(t => t.id === id);
  if (idx === -1) return null;
  const [removed] = db.tasks.splice(idx, 1);
  mutateLogActivity(db, userId, username, "Xóa Task", `Đã xóa công việc "${removed.title}".`);
  return removed;
}

// ---------------------------------------------------------------------------
// Lịch
// ---------------------------------------------------------------------------

/** Tạo sự kiện (giống nhánh tạo của POST /api/plans) + nhật ký + thông báo chung. */
export function mutateCreatePlan(
  db: FamilyOrganizerDB,
  planData: Partial<FamilyPlan>,
  userId: string,
  username: string,
  notices: Notification[] = []
): FamilyPlan {
  const newPlan: FamilyPlan = {
    id: newId("plan"),
    title: planData.title || "Kế hoạch mới",
    description: planData.description || "",
    startDate: planData.startDate || new Date().toISOString().slice(0, 16).replace("T", " "),
    // Sự kiện lặp lại bỏ trống ngày kết thúc = lặp VÔ HẠN → giữ "" (KHÔNG ép về giờ hiện tại).
    // Sự kiện 1 lần không có mốc kết thúc → mặc định +1 giờ để vẽ khoảng hợp lý.
    endDate: (typeof planData.endDate === "string" && planData.endDate.trim())
      ? planData.endDate.trim()
      : (planData.isRecurring ? "" : new Date(Date.now() + 3600000).toISOString().slice(0, 16).replace("T", " ")),
    isRecurring: planData.isRecurring || false,
    recurrenceType: planData.recurrenceType || "none",
    // Lưu các thứ trong tuần cho lịch lặp hằng tuần (vd chọn Thứ 4 dù bắt đầu Thứ 5).
    // Thiếu dòng này thì CREATE bỏ mất → hệ thống lặp nhầm theo thứ của ngày bắt đầu.
    recurrenceWeekdays: Array.isArray(planData.recurrenceWeekdays)
      ? planData.recurrenceWeekdays.map((d: unknown) => Number(d)).filter((d: number) => Number.isInteger(d) && d >= 0 && d <= 6)
      : undefined,
    creatorId: userId,
    isShared: planData.isShared !== undefined ? planData.isShared : true,
    color: planData.color || "sky",
    createdAt: new Date().toISOString()
  };

  db.plans.push(newPlan);
  mutateLogActivity(db, userId, username, "Tạo Lịch trình", `Đã lập lịch trình mới: "${newPlan.title}".`);
  if (newPlan.isShared) {
    notices.push(mutateAddNotification(db, "all", "Sự kiện gia đình mới", `Lịch gia đình có sự kiện mới: "${newPlan.title}" vào ngày ${newPlan.startDate.substring(0, 10)}`));
  }
  return newPlan;
}

/** Sửa sự kiện: MERGE `{...cũ, ...changes}` (giống nhánh sửa của POST /api/plans) + nhật ký. */
export function mutateUpdatePlan(
  db: FamilyOrganizerDB,
  id: string,
  changes: Partial<FamilyPlan>,
  userId: string,
  username: string
): FamilyPlan {
  const idx = db.plans.findIndex(p => p.id === id);
  if (idx === -1) throw new Error("Kế hoạch không tồn tại");
  const updated = { ...db.plans[idx], ...changes } as FamilyPlan;
  db.plans[idx] = updated;
  mutateLogActivity(db, userId, username, "Cập nhật Lịch trình", `Đã cập nhật sự kiện "${updated.title}".`);
  return updated;
}

/** Xoá sự kiện + nhật ký. Không tồn tại → null (giống DELETE /api/plans/:id). */
export function mutateDeletePlan(db: FamilyOrganizerDB, id: string, userId: string, username: string): FamilyPlan | null {
  const idx = db.plans.findIndex(p => p.id === id);
  if (idx === -1) return null;
  const [removed] = db.plans.splice(idx, 1);
  mutateLogActivity(db, userId, username, "Xóa Lịch trình", `Đã xóa sự kiện "${removed.title}".`);
  return removed;
}

// ---------------------------------------------------------------------------
// Thu chi
// ---------------------------------------------------------------------------

const TX_CATEGORY_LABELS: Record<string, string> = {
  food: "Ăn uống", education2: "Học tập", utilities: "Điện nước", shopping: "Mua sắm", medical: "Y tế",
  transport: "Đi lại", debt_bank: "Trả nợ NH", debt_personal: "Trả nợ CN",
  funeral: "Ma chay", ceremony: "Hiếu hỉ", rent: "Thuê nhà", internet: "Cước Internet",
  phone: "Điện thoại", insurance: "Bảo hiểm", loan: "Trả nợ NH", other: "Khác"
};
const TX_ACCOUNT_LABELS: Record<string, string> = {
  cash: "Tiền mặt", bank: "Ngân hàng", e_wallet: "Ví điện tử"
};

const vnd = (n: unknown) => Number(n).toLocaleString("vi-VN");

/** Các thay đổi "cũ → mới" giữa 2 bản giao dịch — để nhật ký minh bạch từng chỉnh sửa. */
export function describeTransactionChanges(oldTx: FinancialTransaction, newTx: FinancialTransaction): string[] {
  const changes: string[] = [];
  if (oldTx.type !== newTx.type)
    changes.push(`loại ${oldTx.type === "income" ? "Thu" : "Chi"} → ${newTx.type === "income" ? "Thu" : "Chi"}`);
  if (oldTx.amount !== newTx.amount)
    changes.push(`số tiền ${vnd(oldTx.amount)} → ${vnd(newTx.amount)} VNĐ`);
  if (oldTx.description !== newTx.description)
    changes.push(`nội dung "${oldTx.description}" → "${newTx.description}"`);
  if (oldTx.date !== newTx.date)
    changes.push(`ngày ${oldTx.date} → ${newTx.date}`);
  if (oldTx.category !== newTx.category)
    changes.push(`hạng mục ${TX_CATEGORY_LABELS[oldTx.category] || oldTx.category} → ${TX_CATEGORY_LABELS[newTx.category] || newTx.category}`);
  if (oldTx.account !== newTx.account)
    changes.push(`ví ${TX_ACCOUNT_LABELS[oldTx.account] || oldTx.account} → ${TX_ACCOUNT_LABELS[newTx.account] || newTx.account}`);
  if ((oldTx.receiptImage || "") !== (newTx.receiptImage || ""))
    changes.push(newTx.receiptImage ? (oldTx.receiptImage ? "thay ảnh hóa đơn" : "thêm ảnh hóa đơn") : "gỡ ảnh hóa đơn");
  return changes;
}

/** Ghi giao dịch mới (giống nhánh tạo của POST /api/finance — cùng mặc định) + nhật ký. */
export function mutateCreateTransaction(
  db: FamilyOrganizerDB,
  txData: Partial<FinancialTransaction>,
  userId: string,
  username: string
): FinancialTransaction {
  const newTx: FinancialTransaction = {
    id: newId("tx"),
    type: txData.type || TransactionType.EXPENSE,
    amount: txData.amount || 0,
    category: txData.category || "other",
    account: txData.account || AccountType.BANK,
    description: txData.description || "",
    date: txData.date || new Date().toISOString().slice(0, 10),
    creatorId: userId,
    receiptImage: txData.receiptImage, // Base64 supported
    createdAt: new Date().toISOString()
  };
  db.transactions.push(newTx);
  mutateLogActivity(db, userId, username, "Ghi chép tài chính",
    `Đã ghi lại ${newTx.type === "expense" ? "khoản chi" : "khoản thu"} "${newTx.description}" (${vnd(newTx.amount)} VNĐ)`);
  return newTx;
}

/** Các trường trợ lý được sửa trên một giao dịch (khớp `finance.update.changes` của hợp đồng). */
export interface TransactionFieldChanges {
  amount?: number;
  category?: string;
  date?: string;
  description?: string;
  account?: "cash" | "bank" | "e_wallet";
}

/**
 * Sửa một số trường của giao dịch: MERGE `{...cũ, ...changes}` — trường không nêu (loại, ảnh hoá đơn, người tạo…)
 * giữ nguyên. Khác FamilyDB.saveTransaction (form gửi nguyên bản ghi, trường thiếu về mặc định + xoá ảnh hoá đơn).
 */
export function mutateUpdateTransaction(
  db: FamilyOrganizerDB,
  id: string,
  changes: TransactionFieldChanges,
  userId: string,
  username: string
): FinancialTransaction {
  const idx = db.transactions.findIndex(t => t.id === id);
  if (idx === -1) throw new Error("Giao dịch không tồn tại");
  const old = db.transactions[idx];
  const patch: Partial<FinancialTransaction> = {};
  for (const [k, v] of Object.entries(changes)) {
    if (v !== undefined) (patch as Record<string, unknown>)[k] = v;
  }
  const updated: FinancialTransaction = { ...old, ...patch };
  db.transactions[idx] = updated;
  const diff = describeTransactionChanges(old, updated);
  mutateLogActivity(db, userId, username, "Sửa giao dịch tài chính",
    diff.length > 0
      ? `Đã sửa giao dịch "${old.description}": ${diff.join("; ")}.`
      : `Đã lưu lại giao dịch "${updated.description}" (không có thay đổi).`);
  return updated;
}

/** Xoá giao dịch + nhật ký. Không tồn tại → null. File hoá đơn do người gọi xoá SAU khi ghi xong. */
export function mutateDeleteTransaction(
  db: FamilyOrganizerDB,
  id: string,
  userId: string,
  username: string
): FinancialTransaction | null {
  const idx = db.transactions.findIndex(t => t.id === id);
  if (idx === -1) return null;
  const [removed] = db.transactions.splice(idx, 1);
  mutateLogActivity(db, userId, username, "Xóa giao dịch tài chính",
    `Đã xóa giao dịch "${removed.description}" (${vnd(removed.amount)} VNĐ).`);
  return removed;
}
