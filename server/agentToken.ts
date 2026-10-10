/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Token ngắn hạn cấp cho agent trong MỘT lượt trò chuyện (red-team C2).
// Agent không bao giờ nhận token đăng nhập của người dùng (token đó không hết hạn,
// không thu hồi được). Token agent:
//   agt.<base64url(userId)>.<exp ms>.<nonce>.<hmac hex>
// - HMAC bằng khoá dẫn xuất từ SESSION_SECRET (khác HMAC của token đăng nhập).
// - Sống 120 s, bị thu hồi ngay khi lượt chạy kết thúc (nonce phải còn trong bộ nhớ).
// - Chỉ hợp lệ cho GET trên đúng 9 endpoint đọc mà tool của agent dùng.

import crypto from "crypto";

/** Khớp ALLOWED_PATHS trong agent/src/family_agent/harness/deps.py — đổi một bên thì đổi cả hai. */
export const AGENT_READ_PATHS: ReadonlySet<string> = new Set([
  "/api/users",
  "/api/tasks",
  "/api/plans",
  "/api/finance",
  "/api/finance/categories",
  "/api/finance/budgets",
  "/api/finance/recurring-bills",
  "/api/shopping",
  "/api/shopping/meal-plan/current",
]);

const PREFIX = "agt.";
const DEFAULT_TTL_MS = 120_000;

export function isAgentToken(token: string): boolean {
  return token.startsWith(PREFIX);
}

export type AgentAuthResult = { ok: true; userId: string } | { ok: false };

export interface AgentTokens {
  issue(userId: string): string;
  revoke(token: string): void;
  authorize(token: string, method: string, path: string): AgentAuthResult;
}

export function createAgentTokens(
  sessionSecret: string,
  opts: { ttlMs?: number; now?: () => number } = {},
): AgentTokens {
  const ttlMs = opts.ttlMs ?? DEFAULT_TTL_MS;
  const now = opts.now ?? Date.now;
  const key = crypto.createHmac("sha256", sessionSecret).update("family-organizer/agent-token/v1").digest();
  const active = new Map<string, number>(); // nonce → exp

  const sign = (payload: string) => crypto.createHmac("sha256", key).update(payload).digest("hex");

  function prune(t: number) {
    for (const [nonce, exp] of active) if (exp <= t) active.delete(nonce);
  }

  function parse(token: string): { userId: string; exp: number; nonce: string } | null {
    if (!isAgentToken(token)) return null;
    const parts = token.split(".");
    if (parts.length !== 5) return null;
    const [, uid, expStr, nonce, sig] = parts;
    if (!uid || !/^\d{1,16}$/.test(expStr) || !/^[a-f0-9]{32}$/.test(nonce) || !/^[a-f0-9]{64}$/.test(sig)) return null;
    const expected = sign(parts.slice(0, 4).join("."));
    if (!crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expected))) return null;
    const userId = Buffer.from(uid, "base64url").toString("utf8");
    return userId ? { userId, exp: Number(expStr), nonce } : null;
  }

  return {
    issue(userId) {
      const t = now();
      prune(t);
      const exp = t + ttlMs;
      const nonce = crypto.randomBytes(16).toString("hex");
      const payload = `agt.${Buffer.from(userId, "utf8").toString("base64url")}.${exp}.${nonce}`;
      active.set(nonce, exp);
      return `${payload}.${sign(payload)}`;
    },
    revoke(token) {
      const nonce = token.split(".")[3];
      if (nonce) active.delete(nonce);
    },
    authorize(token, method, path) {
      const parsed = parse(token);
      if (!parsed) return { ok: false };
      const t = now();
      if (parsed.exp <= t || active.get(parsed.nonce) !== parsed.exp) return { ok: false };
      if (method !== "GET" || !AGENT_READ_PATHS.has(path)) return { ok: false };
      return { ok: true, userId: parsed.userId };
    },
  };
}
