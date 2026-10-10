/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from "vitest";
import { UserRole } from "../types.js";
import { canSeeTask, canSeePlan, canSeeFinance } from "./visibility.js";

const viewer = (id: string, role: UserRole) => ({ id, role });

const task = (o: { creatorId: string; assigneeId?: string | null; isShared: boolean }) => ({
  creatorId: o.creatorId,
  assigneeId: o.assigneeId ?? null,
  isShared: o.isShared
});

const plan = (o: { creatorId: string; isShared: boolean }) => o;

describe("canSeeTask — khớp luật lọc ở Tasks.tsx", () => {
  const privateOfMom = task({ creatorId: "mom", assigneeId: "dad", isShared: false });

  it("admin/member thấy cả việc riêng của người khác (giữ nguyên hành vi UI)", () => {
    expect(canSeeTask(privateOfMom, viewer("grandpa", UserRole.ADMIN))).toBe(true);
    expect(canSeeTask(privateOfMom, viewer("aunt", UserRole.MEMBER))).toBe(true);
  });

  it("con/khách thấy việc chung", () => {
    const shared = task({ creatorId: "mom", isShared: true });
    expect(canSeeTask(shared, viewer("kid", UserRole.CHILD))).toBe(true);
    expect(canSeeTask(shared, viewer("guest", UserRole.GUEST))).toBe(true);
  });

  it("con/khách KHÔNG thấy việc riêng không liên quan tới mình", () => {
    expect(canSeeTask(privateOfMom, viewer("kid", UserRole.CHILD))).toBe(false);
    expect(canSeeTask(privateOfMom, viewer("guest", UserRole.GUEST))).toBe(false);
  });

  it("con thấy việc riêng do mình tạo hoặc được giao", () => {
    expect(canSeeTask(task({ creatorId: "kid", isShared: false }), viewer("kid", UserRole.CHILD))).toBe(true);
    expect(canSeeTask(task({ creatorId: "mom", assigneeId: "kid", isShared: false }), viewer("kid", UserRole.CHILD))).toBe(true);
  });
});

describe("canSeePlan — khớp luật lọc ở Schedules.tsx", () => {
  const privateOfMom = plan({ creatorId: "mom", isShared: false });

  it("admin thấy cả lịch riêng của người khác", () => {
    expect(canSeePlan(privateOfMom, viewer("dad", UserRole.ADMIN))).toBe(true);
  });

  it("member/con/khách KHÔNG thấy lịch riêng của người khác", () => {
    expect(canSeePlan(privateOfMom, viewer("aunt", UserRole.MEMBER))).toBe(false);
    expect(canSeePlan(privateOfMom, viewer("kid", UserRole.CHILD))).toBe(false);
    expect(canSeePlan(privateOfMom, viewer("guest", UserRole.GUEST))).toBe(false);
  });

  it("mọi role thấy lịch chung và lịch mình tạo", () => {
    for (const role of [UserRole.ADMIN, UserRole.MEMBER, UserRole.CHILD, UserRole.GUEST]) {
      expect(canSeePlan(plan({ creatorId: "x", isShared: true }), viewer("me", role))).toBe(true);
      expect(canSeePlan(plan({ creatorId: "me", isShared: false }), viewer("me", role))).toBe(true);
    }
  });
});

describe("canSeeFinance — khớp requireRole của /api/finance", () => {
  it("chỉ admin/member", () => {
    expect(canSeeFinance(UserRole.ADMIN)).toBe(true);
    expect(canSeeFinance(UserRole.MEMBER)).toBe(true);
    expect(canSeeFinance(UserRole.CHILD)).toBe(false);
    expect(canSeeFinance(UserRole.GUEST)).toBe(false);
  });
});
