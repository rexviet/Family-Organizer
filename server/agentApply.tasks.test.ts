/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Apply đề xuất Việc + Lịch (M2): merge không mất trường, guard updatedAt/fingerprint, ma trận quyền
// khớp endpoint gốc (POST/DELETE /api/tasks, /api/plans), ngày thật + kết thúc ≥ bắt đầu.

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";
import { AgentStore } from "./agentStore.js";
import { applyProposal, type ApplyDeps, type ApplySession } from "./agentApply.js";
import { fingerprint, planHash, type AgentOperation } from "./agentContract.js";
import type { FamilyOrganizerDB, FamilyPlan, Notification, Task, User } from "../src/types.js";
import { TaskPriority, TaskStatus, UserRole } from "../src/types.js";

const T0 = Date.parse("2026-10-10T10:00:00.000Z");
const U0 = "2026-10-01T00:00:00.000Z";

const ADMIN: ApplySession = { userId: "u_admin", username: "admin", role: UserRole.ADMIN };
const MEMBER: ApplySession = { userId: "u_mem", username: "mem", role: UserRole.MEMBER };
const KID: ApplySession = { userId: "u_kid", username: "kid", role: UserRole.CHILD };
const GUEST: ApplySession = { userId: "u_guest", username: "guest", role: UserRole.GUEST };

type Mem = Pick<FamilyOrganizerDB, "shoppingItems" | "activityLogs" | "tasks" | "plans" | "users" | "notifications">;

let dir: string;
let store: AgentStore;
let mem: Mem;
let writes: number;
let pushed: Notification[];
let deps: ApplyDeps;

type DbUser = FamilyOrganizerDB["users"][number];

function user(id: string, role: UserRole, extra: Partial<User> = {}): DbUser {
  return { id, username: id, fullName: id.toUpperCase(), role, passwordHash: "x", createdAt: U0, ...extra } as DbUser;
}

function task(id: string, extra: Partial<Task> = {}): Task {
  return {
    id, title: `Việc ${id}`, description: "mô tả cũ", status: TaskStatus.TODO, priority: TaskPriority.MEDIUM,
    dueDate: "2026-10-12 17:00", creatorId: "u_admin", assigneeId: null, isShared: true, tags: ["nhà"],
    rewardPoints: 20, recurrenceType: "weekly", recurrenceInterval: 1, comments: [{ id: "c", userId: "u", username: "u", content: "hi", createdAt: U0 }],
    history: [], createdAt: U0, updatedAt: U0, ...extra,
  } as Task;
}

function plan(id: string, extra: Partial<FamilyPlan> = {}): FamilyPlan {
  return {
    id, title: `Lịch ${id}`, description: "", startDate: "2026-10-12 08:00", endDate: "2026-10-12 10:00",
    isRecurring: false, recurrenceType: "none", creatorId: "u_admin", isShared: true, color: "rose", createdAt: U0, ...extra,
  };
}

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "fo-agent-apply-tp-"));
  store = new AgentStore(path.join(dir, "agent.db"));
  mem = {
    shoppingItems: [], activityLogs: [], notifications: [],
    users: [
      user("u_admin", UserRole.ADMIN), user("u_mem", UserRole.MEMBER), user("u_kid", UserRole.CHILD),
      user("u_guest", UserRole.GUEST), user("u_gone", UserRole.MEMBER, { isDeleted: true }),
    ],
    tasks: [
      task("t1"),
      task("t_kid_own", { creatorId: "u_kid", assigneeId: "u_kid" }),
      task("t_kid_assigned", { creatorId: "u_admin", assigneeId: "u_kid" }),
      task("t_pending", { assigneeId: "u_kid", status: TaskStatus.IN_PROGRESS, pendingApproval: true }),
      task("t_done", { status: TaskStatus.COMPLETED, completedById: "u_admin", completedAt: U0 }),
    ],
    plans: [
      plan("p1"),
      plan("p_kid", { creatorId: "u_kid" }),
      plan("p_weekly", { isRecurring: true, recurrenceType: "weekly", recurrenceWeekdays: [1], endDate: "" }),
    ],
  };
  writes = 0;
  pushed = [];
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
    afterCommit: (notifications) => { pushed.push(...notifications); },
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
const B = (updatedAt = U0) => ({ updatedAt });
const FP = (id: string) => ({ fingerprint: fingerprint("plan", mem.plans.find((p) => p.id === id)!) });
const T = (id: string) => mem.tasks.find((t) => t.id === id)!;
const P = (id: string) => mem.plans.find((p) => p.id === id)!;

describe("task.create", () => {
  it("tạo việc, người tạo = người duyệt, giao người khác thì có thông báo (đẩy sau khi ghi)", () => {
    const { r } = apply([{ type: "task.create", title: "Đổ rác", dueDate: "2026-10-15 18:00", assigneeId: "u_kid", priority: "high", rewardPoints: 10 }], ADMIN);
    expect(r).toMatchObject({ ok: true, status: 200, modules: ["TASKS_UPDATE"] });
    const t = mem.tasks.find((x) => x.title === "Đổ rác")!;
    expect(t).toMatchObject({ creatorId: "u_admin", assigneeId: "u_kid", priority: "high", rewardPoints: 10, status: "todo", dueDate: "2026-10-15 18:00", isShared: true });
    expect(mem.notifications.some((n) => n.userId === "u_kid")).toBe(true);
    expect(pushed.map((n) => n.userId)).toEqual(["u_kid"]);
    expect(writes).toBe(1);
  });
  it("hạn chỉ có ngày → cuối ngày 23:59", () => {
    apply([{ type: "task.create", title: "Nộp học phí", dueDate: "2026-10-20" }], MEMBER);
    expect(mem.tasks.find((x) => x.title === "Nộp học phí")?.dueDate).toBe("2026-10-20 23:59");
  });
  it("ngày không có thật → 422 invalid, không ghi", () => {
    const { r } = apply([{ type: "task.create", title: "x", dueDate: "2026-02-30" }], ADMIN);
    expect(r).toMatchObject({ status: 422, code: "invalid" });
    expect(writes).toBe(0);
  });
  it("giao cho người không tồn tại / đã xoá → 422", () => {
    expect(apply([{ type: "task.create", title: "x", assigneeId: "u_nope" }], ADMIN).r).toMatchObject({ status: 422, code: "invalid" });
    expect(apply([{ type: "task.create", title: "x", assigneeId: "u_gone" }], ADMIN).r).toMatchObject({ status: 422, code: "invalid" });
  });
  it("trẻ/khách tạo việc được, nhưng không tự đặt điểm thưởng → 403", () => {
    expect(apply([{ type: "task.create", title: "Tự học" }], KID).r.status).toBe(200);
    expect(apply([{ type: "task.create", title: "Khách" }], GUEST).r.status).toBe(200);
    expect(apply([{ type: "task.create", title: "Điểm", rewardPoints: 50 }], KID).r).toMatchObject({ status: 403, code: "forbidden" });
  });
});

describe("task.update", () => {
  it("merge: chỉ đổi trường trong changes, giữ nguyên comments/tags/điểm/lặp; ghi lịch sử giao việc", () => {
    const { r } = apply([{ type: "task.update", taskId: "t1", base: B(), changes: { dueDate: "2026-10-14 17:00", assigneeId: "u_kid" } }], MEMBER);
    expect(r.status).toBe(200);
    const t = T("t1");
    expect(t).toMatchObject({ dueDate: "2026-10-14 17:00", assigneeId: "u_kid", description: "mô tả cũ", rewardPoints: 20, recurrenceType: "weekly", tags: ["nhà"], creatorId: "u_admin" });
    expect(t.comments).toHaveLength(1);
    expect(t.updatedAt).not.toBe(U0);
    expect(t.history[0].action).toContain("KID");
  });
  it("hạn chỉ có ngày → giữ giờ cũ", () => {
    apply([{ type: "task.update", taskId: "t1", base: B(), changes: { dueDate: "2026-10-14" } }], ADMIN);
    expect(T("t1").dueDate).toBe("2026-10-14 17:00");
  });
  it("guard lệch (vừa có người sửa) → 409 conflict, không ghi", () => {
    const { r } = apply([{ type: "task.update", taskId: "t1", base: B("2026-09-01T00:00:00.000Z"), changes: { title: "x" } }], ADMIN);
    expect(r).toMatchObject({ status: 409, code: "conflict" });
    expect(writes).toBe(0);
  });
  it("việc không còn → 409", () => {
    expect(apply([{ type: "task.update", taskId: "gone", base: B(), changes: { title: "x" } }], ADMIN).r.status).toBe(409);
  });
  it("con sửa việc người khác → 403; sửa việc mình tạo → được", () => {
    expect(apply([{ type: "task.update", taskId: "t1", base: B(), changes: { title: "hack" } }], KID).r).toMatchObject({ status: 403, code: "forbidden" });
    expect(T("t1").title).toBe("Việc t1");
    expect(apply([{ type: "task.update", taskId: "t_kid_own", base: B(), changes: { title: "Học bài" } }], KID).r.status).toBe(200);
  });
  it("con chỉ được giao (không phải người tạo): chỉ đổi trạng thái", () => {
    expect(apply([{ type: "task.update", taskId: "t_kid_assigned", base: B(), changes: { dueDate: "2026-12-01 10:00" } }], KID).r.status).toBe(403);
    expect(apply([{ type: "task.update", taskId: "t_kid_assigned", base: B(), changes: { status: "in_progress" } }], KID).r.status).toBe(200);
    expect(T("t_kid_assigned").status).toBe("in_progress");
  });
  it("việc đang chờ duyệt → 403 (không duyệt/trả qua trợ lý)", () => {
    expect(apply([{ type: "task.update", taskId: "t_pending", base: B(), changes: { status: "todo" } }], ADMIN).r).toMatchObject({ status: 403, code: "forbidden" });
    expect(T("t_pending").pendingApproval).toBe(true);
  });
  it("đổi trạng thái việc đã hoàn thành → 403; sửa tên thì được", () => {
    expect(apply([{ type: "task.update", taskId: "t_done", base: B(), changes: { status: "todo" } }], ADMIN).r.status).toBe(403);
    expect(apply([{ type: "task.update", taskId: "t_done", base: B(), changes: { title: "Đã xong" } }], ADMIN).r.status).toBe(200);
    expect(T("t_done")).toMatchObject({ status: "completed", title: "Đã xong", completedById: "u_admin" });
  });
  it("bỏ giao (assigneeId null) được; giao người lạ → 422", () => {
    expect(apply([{ type: "task.update", taskId: "t_kid_assigned", base: B(), changes: { assigneeId: null } }], ADMIN).r.status).toBe(200);
    expect(T("t_kid_assigned").assigneeId).toBeNull();
    expect(apply([{ type: "task.update", taskId: "t1", base: B(), changes: { assigneeId: "u_nope" } }], ADMIN).r.status).toBe(422);
  });
  it("một bản ghi xuất hiện hai lần trong đề xuất → 422, không ghi", () => {
    const { r } = apply([
      { type: "task.update", taskId: "t1", base: B(), changes: { title: "a" } },
      { type: "task.delete", taskId: "t1", base: B() },
    ], ADMIN);
    expect(r).toMatchObject({ status: 422, code: "invalid" });
    expect(writes).toBe(0);
  });
});

describe("task.delete", () => {
  it("admin/thành viên xoá được", () => {
    expect(apply([{ type: "task.delete", taskId: "t1", base: B() }], MEMBER).r.status).toBe(200);
    expect(mem.tasks.some((t) => t.id === "t1")).toBe(false);
  });
  it("con/khách không xoá được việc (kể cả việc mình tạo) → 403", () => {
    expect(apply([{ type: "task.delete", taskId: "t_kid_own", base: B() }], KID).r.status).toBe(403);
    expect(apply([{ type: "task.delete", taskId: "t1", base: B() }], GUEST).r.status).toBe(403);
    expect(mem.tasks).toHaveLength(5);
  });
  it("guard lệch → 409", () => {
    expect(apply([{ type: "task.delete", taskId: "t1", base: B("x") }], ADMIN).r.status).toBe(409);
  });
});

describe("plan.create", () => {
  it("tạo sự kiện; lặp hằng tuần → isRecurring + thứ lặp", () => {
    const { r } = apply([{
      type: "plan.create", title: "Học bơi", startDate: "2026-10-13 18:00", endDate: "2027-10-13 19:00",
      recurrenceType: "weekly", recurrenceWeekdays: [2],
    }], KID);
    expect(r).toMatchObject({ status: 200, modules: ["PLANS_UPDATE"] });
    expect(mem.plans.find((p) => p.title === "Học bơi")).toMatchObject({
      creatorId: "u_kid", isRecurring: true, recurrenceType: "weekly", recurrenceWeekdays: [2], isShared: true,
    });
  });
  it("khách không tạo lịch → 403", () => {
    expect(apply([{ type: "plan.create", title: "x", startDate: "2026-10-13 18:00", endDate: "2026-10-13 19:00" }], GUEST).r.status).toBe(403);
  });
  it("kết thúc trước bắt đầu / ngày không có thật → 422", () => {
    expect(apply([{ type: "plan.create", title: "x", startDate: "2026-10-13 18:00", endDate: "2026-10-13 17:00" }], ADMIN).r.status).toBe(422);
    expect(apply([{ type: "plan.create", title: "x", startDate: "2026-13-01 18:00", endDate: "2026-13-01 19:00" }], ADMIN).r.status).toBe(422);
    expect(apply([{ type: "plan.create", title: "x", startDate: "2026-10-13 25:00", endDate: "2026-10-13 26:00" }], ADMIN).r.status).toBe(422);
  });
  it("thứ lặp mà không lặp hằng tuần → 422", () => {
    expect(apply([{ type: "plan.create", title: "x", startDate: "2026-10-13 18:00", endDate: "2026-10-13 19:00", recurrenceWeekdays: [1] }], ADMIN).r.status).toBe(422);
  });
});

describe("plan.update", () => {
  it("merge: dời giờ, giữ màu/mô tả/người tạo", () => {
    const { r } = apply([{ type: "plan.update", planId: "p1", base: FP("p1"), changes: { startDate: "2026-10-13 08:00", endDate: "2026-10-13 10:00" } }], ADMIN);
    expect(r.status).toBe(200);
    expect(P("p1")).toMatchObject({ startDate: "2026-10-13 08:00", endDate: "2026-10-13 10:00", color: "rose", creatorId: "u_admin", title: "Lịch p1" });
  });
  it("fingerprint lệch → 409", () => {
    const { r } = apply([{ type: "plan.update", planId: "p1", base: { fingerprint: "0".repeat(64) }, changes: { title: "x" } }], ADMIN);
    expect(r).toMatchObject({ status: 409, code: "conflict" });
  });
  it("thành viên sửa lịch của admin → 403; con sửa lịch mình tạo → được", () => {
    expect(apply([{ type: "plan.update", planId: "p1", base: FP("p1"), changes: { title: "x" } }], MEMBER).r.status).toBe(403);
    expect(apply([{ type: "plan.update", planId: "p_kid", base: FP("p_kid"), changes: { title: "Sinh nhật bạn" } }], KID).r.status).toBe(200);
  });
  it("kết thúc (sau merge) trước bắt đầu → 422", () => {
    expect(apply([{ type: "plan.update", planId: "p1", base: FP("p1"), changes: { startDate: "2026-10-12 11:00" } }], ADMIN).r.status).toBe(422);
  });
  it("lịch lặp vô hạn (endDate rỗng): dời giờ bắt đầu được", () => {
    expect(apply([{ type: "plan.update", planId: "p_weekly", base: FP("p_weekly"), changes: { startDate: "2026-10-12 09:00" } }], ADMIN).r.status).toBe(200);
    expect(P("p_weekly")).toMatchObject({ startDate: "2026-10-12 09:00", endDate: "", recurrenceWeekdays: [1] });
  });
  it("đổi sang không lặp → isRecurring false, bỏ thứ lặp", () => {
    apply([{ type: "plan.update", planId: "p_weekly", base: FP("p_weekly"), changes: { recurrenceType: "none", endDate: "2026-10-12 10:00" } }], ADMIN);
    expect(P("p_weekly")).toMatchObject({ isRecurring: false, recurrenceType: "none" });
    expect(P("p_weekly").recurrenceWeekdays).toBeUndefined();
  });
});

describe("plan.delete", () => {
  it("thành viên xoá lịch của admin → 403, không ghi", () => {
    expect(apply([{ type: "plan.delete", planId: "p1", base: FP("p1") }], MEMBER).r).toMatchObject({ status: 403, code: "forbidden" });
    expect(writes).toBe(0);
  });
  it("admin xoá được; fingerprint lệch → 409", () => {
    expect(apply([{ type: "plan.delete", planId: "p_kid", base: { fingerprint: "1".repeat(64) } }], ADMIN).r.status).toBe(409);
    expect(apply([{ type: "plan.delete", planId: "p_kid", base: FP("p_kid") }], ADMIN).r.status).toBe(200);
    expect(mem.plans.some((p) => p.id === "p_kid")).toBe(false);
  });
});

it("đề xuất trộn đi chợ + việc + lịch: một lần ghi, broadcast đủ module", () => {
  const { r } = apply([
    { type: "shopping.add", items: [{ name: "Sữa" }] },
    { type: "task.create", title: "Mua quà" },
    { type: "plan.delete", planId: "p1", base: FP("p1") },
  ], ADMIN);
  expect(r).toMatchObject({ status: 200, modules: ["SHOPPING_UPDATE", "TASKS_UPDATE", "PLANS_UPDATE"] });
  expect(writes).toBe(1);
});
