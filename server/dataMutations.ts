/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Hàm sửa dữ liệu THUẦN: chỉ sửa trên một bản FamilyOrganizerDB đã đọc, không đọc/ghi SQLite.
// Dùng chung cho endpoint thường (FamilyDB.save*/delete*) và apply đề xuất của trợ lý
// (FamilyDB.applyBatch) để hai đường ghi không lệch nhau. File không có side effect khi import.

import crypto from "crypto";
import type { FamilyOrganizerDB, FamilyPlan, Notification, ShoppingItem, Task } from "../src/types.js";

/** ID mới: tiền tố + thời gian + hậu tố ngẫu nhiên — ghi nhiều bản ghi liền nhau không trùng. */
export function newId(prefix: string): string {
  return `${prefix}_${Date.now()}_${crypto.randomBytes(6).toString("hex")}`;
}

const MAX_ACTIVITY_LOGS = 300;
const MAX_NOTIFICATIONS = 200;

function mutateLogActivity(db: FamilyOrganizerDB, userId: string, username: string, action: string, details: string): void {
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
