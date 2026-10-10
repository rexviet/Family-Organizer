/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";
import { AgentStore } from "./agentStore.js";
import type { AgentOperation } from "./agentContract.js";

const DAY = 24 * 3600 * 1000;
const T0 = Date.parse("2026-10-10T10:00:00.000Z");
const ops: AgentOperation[] = [{ type: "shopping.add", items: [{ name: "sữa" }] }];

let dir: string;
let store: AgentStore;

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "fo-agent-store-"));
  store = new AgentStore(path.join(dir, "agent.db"));
});
afterEach(() => {
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

function proposal(userId = "u1", conversationId = "c1", at = T0) {
  return store.createProposal({ conversationId, userId, operations: ops, planHash: "h1", preview: [] }, at);
}

describe("hội thoại", () => {
  it("tạo, lấy mới nhất của đúng người, lưu history + turns", () => {
    const a = store.createConversation("u1", T0);
    store.createConversation("u2", T0 + 1000);
    const b = store.createConversation("u1", T0 + 2000);
    expect(store.latestConversation("u1")?.id).toBe(b.id);
    expect(store.latestConversation("u3")).toBeUndefined();

    store.saveConversation(a.id, [{ kind: "request" }], [{ role: "user", text: "chào", at: "x" }], T0 + 5000);
    const got = store.getConversation(a.id)!;
    expect(got.messages).toEqual([{ kind: "request" }]);
    expect(got.turns).toEqual([{ role: "user", text: "chào", at: "x" }]);
    expect(store.latestConversation("u1")?.id).toBe(a.id); // cập nhật gần nhất
  });

  it("file nằm đúng chỗ được chỉ định và mở lại vẫn còn dữ liệu", () => {
    const c = store.createConversation("u1", T0);
    store.close();
    store = new AgentStore(path.join(dir, "agent.db"));
    expect(store.getConversation(c.id)?.userId).toBe("u1");
  });
});

describe("proposal", () => {
  it("tạo pending, hết hạn sau 30 phút", () => {
    const p = proposal();
    expect(p.status).toBe("pending");
    expect(Date.parse(p.expiresAt) - T0).toBe(30 * 60 * 1000);
    expect(store.getProposal(p.id)?.operations).toEqual(ops);
  });

  it("beginApply chỉ thành công một lần (pending → applying có điều kiện)", () => {
    const p = proposal();
    expect(store.beginApply(p.id)).toBe(true);
    expect(store.beginApply(p.id)).toBe(false);
    store.finishApply(p.id, "applied", [{ index: 0, ok: true }], T0 + 1);
    const got = store.getProposal(p.id)!;
    expect(got.status).toBe("applied");
    expect(got.results).toEqual([{ index: 0, ok: true }]);
    expect(got.appliedAt).toBeTruthy();
  });

  it("khởi động lại: applying → failed (không chạy lại)", () => {
    const p = proposal();
    store.beginApply(p.id);
    expect(store.failStaleApplying(T0)).toBe(1);
    const got = store.getProposal(p.id)!;
    expect(got.status).toBe("failed");
    expect(got.error).toMatch(/kiểm tra lại/);
  });

  it("huỷ: chỉ chủ sở hữu, chỉ khi pending", () => {
    const p = proposal();
    expect(store.cancel(p.id, "u2")).toBe(false);
    expect(store.cancel(p.id, "u1")).toBe(true);
    expect(store.getProposal(p.id)?.status).toBe("cancelled");
    expect(store.cancel(p.id, "u1")).toBe(false);
  });

  it("listByConversation trả các proposal của hội thoại", () => {
    proposal("u1", "c1");
    proposal("u1", "c2");
    expect(store.listProposals("c1").length).toBe(1);
  });
});

describe("dọn dẹp + đổi quyền", () => {
  it("hội thoại > 30 ngày không hoạt động và proposal > 7 ngày bị xoá; pending quá hạn → expired", () => {
    const old = store.createConversation("u1", T0 - 31 * DAY);
    const fresh = store.createConversation("u1", T0 - 29 * DAY);
    const oldP = proposal("u1", fresh.id, T0 - 8 * DAY);
    const staleP = proposal("u1", fresh.id, T0 - 60 * 60 * 1000);
    const newP = proposal("u1", fresh.id, T0);
    const r = store.cleanup(T0);
    expect(r).toMatchObject({ conversations: 1, proposals: 1 });
    expect(store.getConversation(old.id)).toBeUndefined();
    expect(store.getConversation(fresh.id)).toBeDefined();
    expect(store.getProposal(oldP.id)).toBeUndefined();
    expect(store.getProposal(staleP.id)?.status).toBe("expired");
    expect(store.getProposal(newP.id)?.status).toBe("pending");
  });

  it("deleteUserData: xoá hội thoại + proposal pending của người đó, giữ của người khác", () => {
    const c = store.createConversation("u1", T0);
    const pending = proposal("u1", c.id);
    const applied = proposal("u1", c.id);
    store.beginApply(applied.id);
    store.finishApply(applied.id, "applied", [], T0);
    const other = proposal("u2", "c9");
    store.deleteUserData("u1");
    expect(store.getConversation(c.id)).toBeUndefined();
    expect(store.getProposal(pending.id)).toBeUndefined();
    expect(store.getProposal(applied.id)?.status).toBe("applied");
    expect(store.getProposal(other.id)).toBeDefined();
  });
});
