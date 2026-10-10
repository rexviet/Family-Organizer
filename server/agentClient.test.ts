/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import http from "http";
import type { AddressInfo } from "net";
import { AgentClient, AgentError, type AgentRunRequest } from "./agentClient.js";

const SECRET = "k".repeat(40);
let server: http.Server;
let base: string;
let handler: (req: http.IncomingMessage, body: string, res: http.ServerResponse) => void;
let healthHits = 0;

function json(res: http.ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

beforeAll(async () => {
  server = http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      if (req.url === "/health") healthHits++;
      handler(req, body, res);
    });
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});
afterAll(() => new Promise<void>((r) => server.close(() => r())));
beforeEach(() => {
  healthHits = 0;
  handler = (_req, _body, res) => json(res, 404, {});
});

const runReq: AgentRunRequest = {
  message: "thêm sữa", history: [], user: { id: "u1", fullName: "Bố", role: "admin" },
  agentToken: "agt.x", today: "2026-10-10", weekday: "Thứ Bảy",
};
const okHealth = { ok: true, llmConfigured: true, model: "m", version: "1.2.0", contractVersion: 1 };

describe("AgentClient", () => {
  it("chưa cấu hình URL/secret → configured=false, health null, không gọi mạng", async () => {
    const c = new AgentClient({ url: "", secret: "" });
    expect(c.configured).toBe(false);
    expect(await c.health()).toBeNull();
  });

  it("health: cache 30 s (cả khi lỗi)", async () => {
    let t = 0;
    handler = (_req, _b, res) => json(res, 200, okHealth);
    const c = new AgentClient({ url: base, secret: SECRET, now: () => t });
    expect(await c.health()).toEqual(okHealth);
    await c.health();
    expect(healthHits).toBe(1);
    t += 31_000;
    await c.health();
    expect(healthHits).toBe(2);
  });

  it("health: không kết nối được → null", async () => {
    const c = new AgentClient({ url: "http://127.0.0.1:1", secret: SECRET });
    expect(await c.health()).toBeNull();
  });

  it("run: gửi X-Agent-Secret + body, nhận proposal", async () => {
    let seen: { secret?: string; body?: unknown } = {};
    handler = (req, body, res) => {
      seen = { secret: req.headers["x-agent-secret"] as string, body: JSON.parse(body) };
      json(res, 200, {
        kind: "proposal", reply: "Mình đề xuất 1 thay đổi", operations: [{ type: "shopping.add", items: [{ name: "sữa" }] }],
        history: [{ kind: "request" }], usage: { requests: 1 }, contractVersion: 1,
      });
    };
    const c = new AgentClient({ url: base, secret: SECRET });
    const r = await c.run(runReq);
    expect(seen.secret).toBe(SECRET);
    expect(seen.body).toEqual(runReq);
    expect(r.kind).toBe("proposal");
    expect(r.operations).toHaveLength(1);
  });

  it("run: lỗi agent → AgentError mang mã của agent", async () => {
    handler = (_req, _b, res) => json(res, 429, { error: "busy" });
    const c = new AgentClient({ url: base, secret: SECRET });
    await expect(c.run(runReq)).rejects.toMatchObject({ code: "busy", httpStatus: 429 });
  });

  it("run: quá timeout → AgentError timeout", async () => {
    handler = (_req, _b, res) => setTimeout(() => json(res, 200, {}), 500);
    const c = new AgentClient({ url: base, secret: SECRET, runTimeoutMs: 50 });
    await expect(c.run(runReq)).rejects.toMatchObject({ code: "timeout" });
  });

  it("run: phản hồi sai hình dạng → invalid_response", async () => {
    handler = (_req, _b, res) => json(res, 200, { kind: "weird", reply: 1 });
    const c = new AgentClient({ url: base, secret: SECRET });
    const err = await c.run(runReq).catch((e) => e);
    expect(err).toBeInstanceOf(AgentError);
    expect(err.code).toBe("invalid_response");
  });

  it("run: không kết nối được → unreachable", async () => {
    const c = new AgentClient({ url: "http://127.0.0.1:1", secret: SECRET });
    await expect(c.run(runReq)).rejects.toMatchObject({ code: "unreachable" });
  });
});
