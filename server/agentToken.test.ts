/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from "vitest";
import crypto from "crypto";
import { AGENT_READ_PATHS, createAgentTokens, isAgentToken } from "./agentToken.js";

const SECRET = "s".repeat(64);

function make(now = { t: 1_000_000 }) {
  return { now, tokens: createAgentTokens(SECRET, { ttlMs: 120_000, now: () => now.t }) };
}

describe("token agent", () => {
  it("có tiền tố agt. và xác thực ra đúng userId (kể cả id có dấu chấm)", () => {
    const { tokens } = make();
    const t = tokens.issue("user.with.dots");
    expect(isAgentToken(t)).toBe(true);
    expect(t.startsWith("agt.")).toBe(true);
    expect(tokens.authorize(t, "GET", "/api/shopping")).toEqual({ ok: true, userId: "user.with.dots" });
  });

  it("hết hạn sau 120 s", () => {
    const { tokens, now } = make();
    const t = tokens.issue("u1");
    now.t += 119_000;
    expect(tokens.authorize(t, "GET", "/api/tasks").ok).toBe(true);
    now.t += 2_000;
    expect(tokens.authorize(t, "GET", "/api/tasks").ok).toBe(false);
  });

  it("thu hồi sau lượt chạy → không dùng lại được", () => {
    const { tokens } = make();
    const t = tokens.issue("u1");
    tokens.revoke(t);
    expect(tokens.authorize(t, "GET", "/api/tasks").ok).toBe(false);
  });

  it("sửa chữ ký / userId / hạn → bị từ chối", () => {
    const { tokens } = make();
    const t = tokens.issue("u1");
    const parts = t.split(".");
    const tamperedSig = [...parts.slice(0, -1), parts[parts.length - 1].replace(/^./, (c) => (c === "a" ? "b" : "a"))].join(".");
    expect(tokens.authorize(tamperedSig, "GET", "/api/tasks").ok).toBe(false);
    const otherUser = ["agt", Buffer.from("admin").toString("base64url"), ...parts.slice(2)].join(".");
    expect(tokens.authorize(otherUser, "GET", "/api/tasks").ok).toBe(false);
    const longer = [parts[0], parts[1], String(Number(parts[2]) + 999_999), ...parts.slice(3)].join(".");
    expect(tokens.authorize(longer, "GET", "/api/tasks").ok).toBe(false);
  });

  it("token của bản cài khác (secret khác) bị từ chối", () => {
    const { tokens } = make();
    const other = createAgentTokens("x".repeat(64), { now: () => 1_000_000 });
    expect(tokens.authorize(other.issue("u1"), "GET", "/api/tasks").ok).toBe(false);
  });

  it("chỉ GET trên allowlist 9 endpoint đọc", () => {
    const { tokens } = make();
    const t = tokens.issue("u1");
    expect(AGENT_READ_PATHS.size).toBe(9);
    for (const p of AGENT_READ_PATHS) expect(tokens.authorize(t, "GET", p).ok).toBe(true);
    for (const [m, p] of [
      ["POST", "/api/shopping"],
      ["DELETE", "/api/shopping/shop_1"],
      ["GET", "/api/users/user_admin"],
      ["GET", "/api/admin/backups"],
      ["GET", "/api/admin/backups/full/export"],
      ["GET", "/api/system/update"],
      ["GET", "/api/settings/ai"],
      ["GET", "/api/settings/agent"],
      ["POST", "/api/assistant/agent"],
      ["GET", "/api/shopping/"],
      ["HEAD", "/api/shopping"],
    ] as const) {
      expect(tokens.authorize(t, m, p).ok, `${m} ${p}`).toBe(false);
    }
  });

  it("chữ ký khác HMAC của token đăng nhập (không dùng làm token đăng nhập được)", () => {
    const { tokens } = make();
    const t = tokens.issue("u1");
    const dot = t.lastIndexOf(".");
    const sessionSig = crypto.createHmac("sha256", SECRET).update(t.slice(0, dot)).digest("hex");
    expect(t.slice(dot + 1)).not.toBe(sessionSig);
  });

  it("chuỗi rác không làm ném lỗi", () => {
    const { tokens } = make();
    for (const junk of ["agt.", "agt....", "agt.%%%.1.2.3", "abc", "agt.dTE.NaN.n.s"]) {
      expect(tokens.authorize(junk, "GET", "/api/tasks").ok).toBe(false);
    }
  });
});

it("allowlist khớp ALLOWED_PATHS của agent (deps.py)", async () => {
  const fs = await import("fs");
  const src = fs.readFileSync(new URL("../agent/src/family_agent/harness/deps.py", import.meta.url), "utf8");
  const block = /ALLOWED_PATHS[^=]*=\s*frozenset\(\{([\s\S]*?)\}\)/.exec(src)?.[1] ?? "";
  const paths = [...block.matchAll(/"([^"]+)"/g)].map((m) => m[1]).sort();
  expect(paths).toEqual([...AGENT_READ_PATHS].sort());
});
