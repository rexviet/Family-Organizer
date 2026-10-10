/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { UserRole, isLimitedViewer } from "../src/types.js";
import type { FamilyPlan, Task } from "../src/types.js";

type Actor = { role: UserRole; userId: string };

const isAdult = (role: UserRole) => role === UserRole.ADMIN || role === UserRole.MEMBER;

/** Tạo việc (POST /api/tasks không kèm id): mọi vai trò đã đăng nhập. */
export function canCreateTask(_session: Actor): boolean {
  return true;
}

/** Xoá việc (DELETE /api/tasks/:id): chỉ Admin/Thành viên. */
export function canDeleteTask(session: Actor): boolean {
  return isAdult(session.role);
}

/** Tạo lịch (POST /api/plans không kèm id): Admin/Thành viên/Trẻ — Khách không. */
export function canCreatePlan(session: Actor): boolean {
  return isAdult(session.role) || session.role === UserRole.CHILD;
}

/**
 * Sửa lịch có sẵn (POST /api/plans kèm id): vai trò được tạo lịch VÀ (người tạo hoặc Admin).
 * Lịch không còn tồn tại thì chỉ xét vai trò (endpoint gốc không chặn).
 */
export function canEditPlan(plan: Pick<FamilyPlan, "creatorId"> | undefined | null, session: Actor): boolean {
  if (!canCreatePlan(session)) return false;
  return !plan || plan.creatorId === session.userId || session.role === UserRole.ADMIN;
}

/** Xoá lịch (DELETE /api/plans/:id): cùng luật với sửa. */
export function canDeletePlan(plan: Pick<FamilyPlan, "creatorId"> | undefined | null, session: Actor): boolean {
  return canEditPlan(plan, session);
}

/**
 * Quyền sửa công việc đã có qua POST /api/tasks.
 * Trẻ/Khách chỉ được sửa việc do mình tạo hoặc được giao; vai trò khác sửa tự do.
 * Việc chưa tồn tại (tạo mới) không bị chặn ở đây. Bình luận đi qua endpoint riêng,
 * nên KHÔNG có ngoại lệ nào theo nội dung body.
 */
export function canEditTask(
  existing: Pick<Task, "creatorId" | "assigneeId"> | undefined | null,
  session: { role: UserRole; userId: string }
): boolean {
  if (!existing) return true;
  if (!isLimitedViewer(session.role)) return true;
  return existing.creatorId === session.userId || existing.assigneeId === session.userId;
}

// Các trường do server quản lý — không bao giờ nhận từ body của POST /api/tasks
// (bình luận có endpoint riêng, duyệt/trả có endpoint riêng, còn lại server tự đặt).
const SERVER_CONTROLLED_FIELDS = [
  "comments", "history", "creatorId", "completedById", "completedAt",
  "pendingApproval", "submittedById", "submittedAt", "rejectionReason",
  "sourceRecurringTaskId", "createdAt", "updatedAt"
] as const;

// Trẻ/Khách chỉ được được giao việc (không phải người tạo) thì chỉ đổi các trường báo hoàn thành.
const ASSIGNEE_ONLY_FIELDS = new Set(["id", "status", "proofImage", "proofNote", "baseUpdatedAt"]);

export type TaskWriteResult =
  | { ok: true; data: Record<string, unknown> }
  | { ok: false; error: string };

/**
 * Làm sạch body của POST /api/tasks theo vai trò. Không mutate body gốc.
 * - Mọi vai trò: bỏ các trường server quản lý.
 * - Trẻ/Khách: không sửa việc của người khác; không tự đặt/đổi rewardPoints
 *   (tránh tự thưởng điểm); nếu chỉ được giao (không phải người tạo) thì chỉ giữ
 *   status/proofImage/proofNote.
 */
export function sanitizeTaskWrite(
  body: Record<string, unknown>,
  existing: Pick<Task, "creatorId" | "assigneeId"> | undefined | null,
  session: { role: UserRole; userId: string }
): TaskWriteResult {
  if (!canEditTask(existing, session)) {
    return { ok: false, error: "Bạn chỉ được sửa đổi công việc do mình tạo hoặc được giao!" };
  }
  const data: Record<string, unknown> = { ...body };
  for (const f of SERVER_CONTROLLED_FIELDS) delete data[f];

  if (isLimitedViewer(session.role)) {
    delete data.rewardPoints;
    if (existing && existing.creatorId !== session.userId) {
      for (const k of Object.keys(data)) {
        if (!ASSIGNEE_ONLY_FIELDS.has(k)) delete data[k];
      }
    }
  }
  return { ok: true, data };
}
