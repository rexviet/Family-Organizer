/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from "vitest";
import { canEditTask, sanitizeTaskWrite } from "./permissions.js";
import { UserRole } from "../src/types.js";

const task = { creatorId: "admin1", assigneeId: null as string | null };
const child = { role: UserRole.CHILD, userId: "kid1" };
const guest = { role: UserRole.GUEST, userId: "guest1" };

describe("canEditTask", () => {
  it("trẻ sửa việc do mình tạo: cho phép", () => {
    expect(canEditTask({ creatorId: "kid1", assigneeId: null }, child)).toBe(true);
  });
  it("trẻ sửa việc được giao cho mình: cho phép", () => {
    expect(canEditTask({ creatorId: "admin1", assigneeId: "kid1" }, child)).toBe(true);
  });
  it("trẻ sửa việc của người khác: chặn (kể cả khi body có comments)", () => {
    expect(canEditTask(task, child)).toBe(false);
  });
  it("khách sửa việc của người khác: chặn", () => {
    expect(canEditTask(task, guest)).toBe(false);
  });
  it("admin/thành viên sửa mọi việc: cho phép", () => {
    expect(canEditTask(task, { role: UserRole.ADMIN, userId: "a" })).toBe(true);
    expect(canEditTask(task, { role: UserRole.MEMBER, userId: "m" })).toBe(true);
  });
  it("việc mới (chưa tồn tại): không bị ảnh hưởng", () => {
    expect(canEditTask(undefined, child)).toBe(true);
    expect(canEditTask(undefined, guest)).toBe(true);
  });
});

describe("sanitizeTaskWrite", () => {
  const assignedToKid = { creatorId: "admin1", assigneeId: "kid1" };
  const ownByKid = { creatorId: "kid1", assigneeId: "kid1" };
  const adm = { role: UserRole.ADMIN, userId: "admin1" };

  it("trẻ sửa việc được giao: chỉ giữ status/proof, bỏ creatorId/rewardPoints/comments/title", () => {
    const r = sanitizeTaskWrite(
      { id: "t", creatorId: "kid1", rewardPoints: 500, title: "x", assigneeId: "kid1", isShared: true,
        comments: [{ userId: "admin", content: "forged" }] },
      assignedToKid, child);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data).toEqual({ id: "t" });
  });
  it("trẻ báo xong việc được giao (status + proof + baseUpdatedAt): giữ nguyên", () => {
    const body = { id: "t", status: "completed", proofImage: "data:x", proofNote: "xong", baseUpdatedAt: "2026-01-01" };
    const r = sanitizeTaskWrite(body, assignedToKid, child);
    expect(r).toEqual({ ok: true, data: body });
  });
  it("trẻ sửa việc của người khác (kể cả có comments): từ chối", () => {
    const r = sanitizeTaskWrite({ id: "t", title: "hacked", comments: [] }, task, child);
    expect(r.ok).toBe(false);
  });
  it("khách sửa việc của người khác: từ chối", () => {
    expect(sanitizeTaskWrite({ id: "t", title: "h" }, task, guest).ok).toBe(false);
  });
  it("trẻ sửa việc do mình tạo: bỏ rewardPoints (không tự tăng điểm), giữ title", () => {
    const r = sanitizeTaskWrite({ id: "t", title: "mới", rewardPoints: 99, creatorId: "x" }, ownByKid, child);
    expect(r).toEqual({ ok: true, data: { id: "t", title: "mới" } });
  });
  it("trẻ tạo việc mới: rewardPoints bị bỏ, creatorId bị bỏ", () => {
    const r = sanitizeTaskWrite({ title: "a", rewardPoints: 50, creatorId: "admin1", comments: [] }, undefined, child);
    expect(r).toEqual({ ok: true, data: { title: "a" } });
  });
  it("admin gửi comments/creatorId/history...: bị bỏ, phần còn lại giữ nguyên", () => {
    const r = sanitizeTaskWrite(
      { id: "t", title: "ok", rewardPoints: 10, assigneeId: "kid1", creatorId: "x", comments: [], history: [],
        completedById: "x", completedAt: "x", pendingApproval: false, submittedById: "x", submittedAt: "x",
        rejectionReason: "x", sourceRecurringTaskId: "x", createdAt: "x", updatedAt: "x" },
      task, adm);
    expect(r).toEqual({ ok: true, data: { id: "t", title: "ok", rewardPoints: 10, assigneeId: "kid1" } });
  });
  it("admin sửa bình thường: không đổi", () => {
    const body = { id: "t", title: "a", status: "in_progress", rewardPoints: 5 };
    expect(sanitizeTaskWrite(body, task, adm)).toEqual({ ok: true, data: body });
  });
  it("không mutate body gốc", () => {
    const body = { id: "t", comments: [], title: "a" };
    sanitizeTaskWrite(body, task, adm);
    expect(body).toHaveProperty("comments");
  });
});
