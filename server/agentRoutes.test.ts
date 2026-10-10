/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import express from "express";
import fs from "fs";
import os from "os";
import path from "path";
import type { AddressInfo } from "net";
import type { Server } from "http";
import { AgentStore } from "./agentStore.js";
import { createAgentTokens } from "./agentToken.js";
import { createAgentRouter, publicProposal, type AgentRouteDeps } from "./agentRoutes.js";
import { AgentError, type AgentHealth, type AgentRunRequest, type AgentRunResponse } from "./agentClient.js";
import { CONTRACT_VERSION } from "./agentContract.js";
import { UserRole, type FamilyOrganizerDB, type ShoppingItem } from "../src/types.js";

const USERS: Record<string, { userId: string; username: string; fullName: string; role: UserRole }> = {
  admin: { userId: "u_admin", username: "admin", fullName: "Bố", role: UserRole.ADMIN },
  kid: { userId: "u_kid", username: "kid", fullName: "Bin", role: UserRole.CHILD },
};

let dir: string;
let store: AgentStore;
let server: Server;
let base: string;
let enabled: boolean;
let health: AgentHealth | null;
let runImpl: (req: AgentRunRequest) => Promise<AgentRunResponse>;
let runCalls: AgentRunRequest[];
// Dạng DB đã normalize (applyBatch luôn đưa bản đầy đủ) — chỉ các mảng mà apply đọc tới.
let mem: Pick<FamilyOrganizerDB, "shoppingItems" | "activityLogs" | "tasks" | "plans" | "users" | "notifications">;
let events: string[];
let tokens: ReturnType<typeof createAgentTokens>;
let previewViewers: unknown[];

const okHealth: AgentHealth = { ok: true, llmConfigured: true, model: "m", version: "1.2.0", contractVersion: CONTRACT_VERSION };

function answer(reply = "Chào bạn", extra: Partial<AgentRunResponse> = {}): AgentRunResponse {
  return { kind: "answer", reply, history: [{ kind: "request", n: runCalls.length }], contractVersion: CONTRACT_VERSION, ...extra };
}

beforeEach(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "fo-agent-routes-"));
  store = new AgentStore(path.join(dir, "agent.db"));
  enabled = true;
  health = okHealth;
  runCalls = [];
  runImpl = async () => answer();
  mem = {
    shoppingItems: [{
      id: "s1", name: "Sữa", isPurchased: false, creatorId: "u_admin", createdAt: "x", updatedAt: "2026-10-01T00:00:00.000Z",
    } as ShoppingItem],
    activityLogs: [], tasks: [], plans: [], users: [], notifications: [],
  };
  events = [];
  previewViewers = [];
  tokens = createAgentTokens("z".repeat(64));

  const deps: AgentRouteDeps = {
    store,
    tokens,
    client: {
      configured: true,
      health: async () => health,
      run: async (req) => { runCalls.push(req); return runImpl(req); },
    },
    requireAuth: (req, res, next) => {
      const u = USERS[String(req.headers["x-test-user"] || "")];
      if (!u) { res.status(401).json({ error: "401" }); return; }
      (req as unknown as { userSession: unknown }).userSession = u;
      next();
    },
    isEnabled: () => enabled,
    setEnabled: (v) => { enabled = v; },
    previewContext: (viewer) => { previewViewers.push(viewer); return { users: [], shoppingItems: mem.shoppingItems, tasks: [], plans: [], transactions: [] }; },
    applyDeps: {
      applyBatch: (fn) => { const copy = structuredClone(mem) as FamilyOrganizerDB; const r = fn(copy); mem = copy; return r; },
    },
    broadcast: (e) => { events.push(e); },
    rateLimit: { max: 3, windowMs: 3600_000 },
  };
  const app = express();
  app.use(express.json());
  app.use(createAgentRouter(deps));
  server = await new Promise<Server>((r) => { const s = app.listen(0, "127.0.0.1", () => r(s)); });
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterEach(async () => {
  await new Promise<void>((r) => server.close(() => r()));
  store.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

async function call(method: string, p: string, user: string | null, body?: unknown) {
  const res = await fetch(base + p, {
    method,
    headers: { "Content-Type": "application/json", ...(user ? { "x-test-user": user } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() as Record<string, any> };
}
const ask = (message: string, user = "kid", extra: Record<string, unknown> = {}) =>
  call("POST", "/api/assistant/agent", user, { message, ...extra });

describe("POST /api/assistant/agent — sẵn sàng / fallback", () => {
  it("chưa đăng nhập → 401", async () => {
    expect((await ask("hi", null as unknown as string)).status).toBe(401);
  });

  it("tắt cờ → 503 fallback, không gọi agent", async () => {
    enabled = false;
    const r = await ask("chào");
    expect(r.status).toBe(503);
    expect(r.body).toMatchObject({ fallback: true, reason: "disabled" });
    expect(runCalls).toHaveLength(0);
  });

  it("agent không kết nối được / chưa cấu hình LLM / lệch contractVersion → 503 fallback", async () => {
    health = null;
    expect((await ask("a")).body).toMatchObject({ fallback: true, reason: "unreachable" });
    health = { ...okHealth, llmConfigured: false };
    expect((await ask("a")).body).toMatchObject({ fallback: true, reason: "llm_not_configured" });
    health = { ...okHealth, contractVersion: CONTRACT_VERSION + 1 };
    expect((await ask("a")).body).toMatchObject({ fallback: true, reason: "contract_mismatch" });
    expect(runCalls).toHaveLength(0);
  });

  it("agent lỗi khi chạy (llm_error/timeout) → 503 fallback; bận → 429 không fallback", async () => {
    runImpl = async () => { throw new AgentError("llm_error", 502); };
    expect((await ask("a")).body).toMatchObject({ fallback: true });
    runImpl = async () => { throw new AgentError("busy", 429); };
    const busy = await ask("a");
    expect(busy.status).toBe(429);
    expect(busy.body.fallback).toBeUndefined();
  });

  it("message rỗng / quá dài → 400", async () => {
    expect((await ask("   ")).status).toBe(400);
    expect((await ask("x".repeat(4001))).status).toBe(400);
  });
});

describe("POST /api/assistant/agent — lượt chạy", () => {
  it("gửi đúng body (token agent, không phải token đăng nhập), lưu history + turns", async () => {
    const r = await ask("chào");
    expect(r.status).toBe(200);
    expect(r.body).toMatchObject({ kind: "answer", reply: "Chào bạn" });
    const sent = runCalls[0];
    expect(sent.user).toEqual({ id: "u_kid", fullName: "Bin", role: "child" });
    expect(sent.agentToken.startsWith("agt.")).toBe(true);
    expect(sent.today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(sent.weekday).toMatch(/^(Thứ|Chủ)/);
    // token bị thu hồi khi lượt kết thúc
    expect(tokens.authorize(sent.agentToken, "GET", "/api/shopping").ok).toBe(false);

    const conv = store.getConversation(r.body.conversationId)!;
    expect(conv.userId).toBe("u_kid");
    expect(conv.messages).toEqual([{ kind: "request", n: 1 }]);
    expect(conv.turns.map((t) => t.role)).toEqual(["user", "assistant"]);

    // lượt sau dùng tiếp hội thoại mới nhất + gửi history cũ
    await ask("tiếp");
    expect(runCalls[1].history).toEqual([{ kind: "request", n: 1 }]);
  });

  it("token agent còn hiệu lực trong lúc agent chạy (chỉ GET allowlist)", async () => {
    let during: boolean[] = [];
    runImpl = async (req) => {
      during = [
        tokens.authorize(req.agentToken, "GET", "/api/shopping").ok,
        tokens.authorize(req.agentToken, "POST", "/api/shopping").ok,
      ];
      return answer();
    };
    await ask("x");
    expect(during).toEqual([true, false]);
  });

  it("conversationId của người khác → 404", async () => {
    const other = store.createConversation("u_admin");
    expect((await ask("x", "kid", { conversationId: other.id })).status).toBe(404);
  });

  it("clarification trả question + options", async () => {
    runImpl = async () => answer("Lan hay bà ngoại?", { kind: "clarification", question: "Lan hay bà ngoại?", options: ["Lan", "Bà ngoại"] });
    const r = await ask("mẹ");
    expect(r.body).toMatchObject({ kind: "clarification", reply: "Lan hay bà ngoại?", options: ["Lan", "Bà ngoại"] });
  });

  it("proposal → validate, lưu, trả preview do Node dựng", async () => {
    runImpl = async () => answer("Mình đề xuất 1 thay đổi", {
      kind: "proposal",
      operations: [{ type: "shopping.add", items: [{ name: "sữa", quantity: "2 hộp" }] }],
    });
    const r = await ask("thêm sữa");
    expect(r.body.kind).toBe("proposal");
    expect(r.body.proposal).toMatchObject({ status: "pending", preview: [{ icon: "🛒", text: "Thêm 1 món: sữa (2 hộp)", tone: "add" }] });
    expect(r.body.proposal.planHash).toMatch(/^[a-f0-9]{64}$/);
    expect(store.getProposal(r.body.proposal.id)?.userId).toBe("u_kid");
  });

  it("proposal sai hợp đồng → không lưu, trả answer báo lỗi", async () => {
    runImpl = async () => answer("x", { kind: "proposal", operations: [{ type: "shopping.add", items: [], hack: 1 }] });
    const r = await ask("thêm");
    expect(r.status).toBe(200);
    expect(r.body.kind).toBe("answer");
    expect(r.body.proposal).toBeUndefined();
  });

  it("phản hồi lệch contractVersion → 503 fallback", async () => {
    runImpl = async () => answer("x", { contractVersion: CONTRACT_VERSION + 1 });
    expect((await ask("x")).body).toMatchObject({ fallback: true });
  });

  it("rate limit theo người (cấu hình 3/giờ) → 429", async () => {
    for (let i = 0; i < 3; i++) expect((await ask(`m${i}`)).status).toBe(200);
    expect((await ask("m4")).status).toBe(429);
    expect((await ask("m4", "admin")).status).toBe(200);
  });

  it("một người chỉ một lượt cùng lúc → 429", async () => {
    let release!: () => void;
    runImpl = () => new Promise((r) => { release = () => r(answer()); });
    const first = ask("a");
    await new Promise((r) => setTimeout(r, 30));
    const second = await ask("b");
    expect(second.status).toBe(429);
    release();
    expect((await first).status).toBe(200);
  });
});

describe("hội thoại", () => {
  it("latest: chỉ của mình; new tạo hội thoại trống", async () => {
    expect((await call("GET", "/api/assistant/conversations/latest", "kid")).body).toMatchObject({ available: true, conversation: null });
    await ask("chào");
    const latest = await call("GET", "/api/assistant/conversations/latest", "kid");
    expect(latest.body.conversation.turns).toHaveLength(2);
    expect(latest.body.conversation.messages).toBeUndefined(); // history thô không gửi xuống trình duyệt
    expect((await call("GET", "/api/assistant/conversations/latest", "admin")).body.conversation).toBeNull();

    const created = await call("POST", "/api/assistant/conversations", "kid");
    expect(created.body.conversation.turns).toEqual([]);
    expect((await call("GET", "/api/assistant/conversations/latest", "kid")).body.conversation.id).toBe(created.body.conversation.id);
  });
});

describe("Duyệt / huỷ", () => {
  async function propose(user = "kid") {
    runImpl = async () => answer("đề xuất", {
      kind: "proposal",
      operations: [
        { type: "shopping.add", items: [{ name: "trứng" }] },
        { type: "shopping.set_purchased", itemId: "s1", purchased: true, base: { updatedAt: "2026-10-01T00:00:00.000Z" } },
      ],
    });
    return (await ask("x", user)).body.proposal as { id: string; planHash: string };
  }

  it("apply → ghi + broadcast SHOPPING_UPDATE; bấm lại idempotent", async () => {
    const p = await propose();
    const r = await call("POST", `/api/assistant/proposals/${p.id}/apply`, "kid", { planHash: p.planHash });
    expect(r.status).toBe(200);
    expect(r.body.proposal.status).toBe("applied");
    expect(mem.shoppingItems.map((i) => i.name)).toContain("trứng");
    expect(events).toEqual(["SHOPPING_UPDATE"]);
    const again = await call("POST", `/api/assistant/proposals/${p.id}/apply`, "kid", { planHash: p.planHash });
    expect(again.status).toBe(200);
    expect(events).toEqual(["SHOPPING_UPDATE"]);
    expect(mem.shoppingItems.filter((i) => i.name === "trứng")).toHaveLength(1);
  });

  it("người khác (admin) bấm Duyệt → 404", async () => {
    const p = await propose();
    expect((await call("POST", `/api/assistant/proposals/${p.id}/apply`, "admin", { planHash: p.planHash })).status).toBe(404);
  });

  it("hash sai → 409", async () => {
    const p = await propose();
    const r = await call("POST", `/api/assistant/proposals/${p.id}/apply`, "kid", { planHash: "0".repeat(64) });
    expect(r).toMatchObject({ status: 409, body: { code: "hash_mismatch" } });
  });

  it("huỷ → cancelled; huỷ của người khác → 404; apply sau huỷ → 409", async () => {
    const p = await propose();
    expect((await call("POST", `/api/assistant/proposals/${p.id}/cancel`, "admin")).status).toBe(404);
    const c = await call("POST", `/api/assistant/proposals/${p.id}/cancel`, "kid");
    expect(c.body.proposal.status).toBe("cancelled");
    expect((await call("POST", `/api/assistant/proposals/${p.id}/apply`, "kid", { planHash: p.planHash })).status).toBe(409);
  });
});

describe("/api/settings/agent", () => {
  it("chỉ admin; GET trạng thái, POST bật/tắt", async () => {
    expect((await call("GET", "/api/settings/agent", "kid")).status).toBe(403);
    const g = await call("GET", "/api/settings/agent", "admin");
    expect(g.body).toEqual({
      enabled: true, configured: true, reachable: true, llmConfigured: true, model: "m", version: "1.2.0",
      contractVersion: CONTRACT_VERSION, contractOk: true,
    });
    const p = await call("POST", "/api/settings/agent", "admin", { enabled: false });
    expect(p.body.enabled).toBe(false);
    expect(enabled).toBe(false);
    expect(events).toContain("SETTINGS_UPDATE");
    expect((await call("POST", "/api/settings/agent", "admin", { enabled: "yes" })).status).toBe(400);
  });
});

describe("lỗi bất ngờ trong route async", () => {
  it("store ném lỗi → 500 JSON, không treo/không làm sập tiến trình; lượt sau vẫn chạy", async () => {
    const orig = store.latestConversation.bind(store);
    store.latestConversation = () => { throw new Error("SQLITE_CORRUPT"); };
    const a = await ask("x");
    expect(a.status).toBe(500);
    expect((await call("GET", "/api/assistant/conversations/latest", "kid")).status).toBe(500);
    store.latestConversation = orig;
    expect((await ask("y")).status).toBe(200); // inflight đã được nhả
  });
});

describe("sau review", () => {
  it("M1: đề xuất loại chưa bật (task/finance) → không lưu, không dựng preview, trả answer", async () => {
    runImpl = async () => answer("x", { kind: "proposal", operations: [{ type: "finance.delete", txId: "tx_1", base: { fingerprint: "a".repeat(64) } }] });
    const r = await ask("xoá khoản chi");
    expect(r.body.kind).toBe("answer");
    expect(r.body.proposal).toBeUndefined();
    expect(previewViewers).toEqual([]);
    expect(r.body.reply).toContain("Thu chi");
  });

  it("M2: đề xuất việc/lịch được lưu + dựng preview", async () => {
    runImpl = async () => answer("x", { kind: "proposal", operations: [{ type: "task.create", title: "Đổ rác" }] });
    const r = await ask("tạo việc đổ rác");
    expect(r.body.kind).toBe("proposal");
    expect(r.body.proposal.preview[0].text).toContain("Đổ rác");
  });

  it("M1: preview dựng theo người hỏi", async () => {
    runImpl = async () => answer("x", { kind: "proposal", operations: [{ type: "shopping.add", items: [{ name: "a" }] }] });
    await ask("thêm a");
    expect(previewViewers).toEqual([{ id: "u_kid", role: "child" }]);
  });

  it("M3: hội thoại bị xoá (đổi vai trò) trong lúc agent chạy → không tạo proposal, 409", async () => {
    runImpl = async (req) => {
      store.deleteUserData(req.user.id);
      return answer("x", { kind: "proposal", operations: [{ type: "shopping.add", items: [{ name: "a" }] }] });
    };
    const r = await ask("thêm a");
    expect(r.status).toBe(409);
    expect(store.latestConversation("u_kid")).toBeUndefined();
  });

  it("L5: trợ lý bị tắt → không Duyệt được đề xuất còn chờ", async () => {
    runImpl = async () => answer("x", { kind: "proposal", operations: [{ type: "shopping.add", items: [{ name: "a" }] }] });
    const p = (await ask("thêm a")).body.proposal;
    enabled = false;
    const r = await call("POST", `/api/assistant/proposals/${p.id}/apply`, "kid", { planHash: p.planHash });
    expect(r).toMatchObject({ status: 409, body: { code: "disabled" } });
    expect(store.getProposal(p.id)?.status).toBe("pending");
  });
});

it("L6: 'Cuộc trò chuyện mới' khi hội thoại mới nhất còn trống → dùng lại, không tạo thêm", async () => {
  const a = await call("POST", "/api/assistant/conversations", "kid");
  const b = await call("POST", "/api/assistant/conversations", "kid");
  expect(b.body.conversation.id).toBe(a.body.conversation.id);
});

it("publicProposal: failed do app khởi động lại giữa lúc ghi → uncertain=true; failed khác → false", () => {
  const conv = store.createConversation("u_kid");
  const mk = () => store.createProposal({ conversationId: conv.id, userId: "u_kid", operations: [], planHash: "h", preview: [] });
  const stale = mk();
  expect(store.beginApply(stale.id)).toBe(true);
  store.failStaleApplying();
  const guard = mk();
  store.markPending(guard.id, "failed", "Dữ liệu đã thay đổi");
  expect(publicProposal(store.getProposal(stale.id)!).uncertain).toBe(true);
  expect(publicProposal(store.getProposal(guard.id)!).uncertain).toBe(false);
  expect(publicProposal(mk()).uncertain).toBe(false);
});
