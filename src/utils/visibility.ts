/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Ai được XEM bản ghi nào — dùng chung cho UI (Tasks/Schedules) và server
// (GET /api/tasks, /api/plans, /api/search, trợ lý AI). Trước đây chỉ UI lọc,
// nên ai gọi thẳng API (hoặc hỏi trợ lý) vẫn thấy việc/lịch riêng của người khác.

import { UserRole, isLimitedViewer } from "../types.js";

export interface Viewer {
  id: string;
  role: UserRole;
}

type TaskLike = { creatorId: string; assigneeId: string | null; isShared: boolean };
type PlanLike = { creatorId: string; isShared: boolean };

// Việc: Con/Khách chỉ thấy việc chung + việc mình tạo/được giao; người lớn thấy hết.
export const canSeeTask = (task: TaskLike, viewer: Viewer): boolean =>
  !isLimitedViewer(viewer.role) ||
  task.isShared ||
  task.creatorId === viewer.id ||
  task.assigneeId === viewer.id;

// Lịch: Admin thấy hết; còn lại chỉ thấy lịch chung + lịch mình tạo.
export const canSeePlan = (plan: PlanLike, viewer: Viewer): boolean =>
  viewer.role === UserRole.ADMIN || plan.isShared || plan.creatorId === viewer.id;

// Thu chi: chỉ Admin/Member (khớp requireRole của /api/finance).
export const canSeeFinance = (role: UserRole): boolean =>
  role === UserRole.ADMIN || role === UserRole.MEMBER;
