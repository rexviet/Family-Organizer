/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Gọi dịch vụ agent (Python) trong mạng compose: GET /health, POST /run (spec §4, agent/README.md).
// Agent chỉ trả đề xuất — Node mới là nơi ghi dữ liệu.

export interface AgentHealth {
  ok: boolean;
  llmConfigured: boolean;
  model: string | null;
  version: string;
  contractVersion: number;
}

export interface AgentRunRequest {
  message: string;
  history: unknown[];
  user: { id: string; fullName: string; role: string };
  agentToken: string;
  today: string;
  weekday: string;
}

export interface AgentRunResponse {
  kind: "answer" | "proposal" | "clarification";
  reply: string;
  operations?: unknown;
  question?: string;
  options?: string[];
  history: unknown[];
  usage?: Record<string, unknown>;
  contractVersion: number;
}

/** Mã lỗi: mã của agent (busy, timeout, llm_error, …) hoặc unreachable / invalid_response / http_<n>. */
export class AgentError extends Error {
  constructor(public code: string, public httpStatus?: number) {
    super(`agent: ${code}`);
    this.name = "AgentError";
  }
}

export interface AgentClientConfig {
  url: string;
  secret: string;
  runTimeoutMs?: number;
  healthTtlMs?: number;
  healthTimeoutMs?: number;
  now?: () => number;
}

const KINDS = new Set(["answer", "proposal", "clarification"]);

function isRunResponse(v: unknown): v is AgentRunResponse {
  if (!v || typeof v !== "object") return false;
  const r = v as Record<string, unknown>;
  if (typeof r.kind !== "string" || !KINDS.has(r.kind) || typeof r.reply !== "string") return false;
  if (!Array.isArray(r.history) || typeof r.contractVersion !== "number") return false;
  if (r.kind === "proposal" && !Array.isArray(r.operations)) return false;
  if (r.kind === "clarification") {
    if (typeof r.question !== "string") return false;
    if (r.options !== undefined && !(Array.isArray(r.options) && r.options.every((o) => typeof o === "string"))) return false;
  }
  return true;
}

function isHealth(v: unknown): v is AgentHealth {
  if (!v || typeof v !== "object") return false;
  const h = v as Record<string, unknown>;
  return typeof h.ok === "boolean" && typeof h.llmConfigured === "boolean" && typeof h.contractVersion === "number";
}

export class AgentClient {
  private readonly url: string;
  private readonly secret: string;
  private readonly runTimeoutMs: number;
  private readonly healthTtlMs: number;
  private readonly healthTimeoutMs: number;
  private readonly now: () => number;
  private cache: { at: number; value: AgentHealth | null } | null = null;

  constructor(cfg: AgentClientConfig) {
    this.url = (cfg.url || "").replace(/\/+$/, "");
    this.secret = cfg.secret || "";
    this.runTimeoutMs = cfg.runTimeoutMs ?? 100_000;
    this.healthTtlMs = cfg.healthTtlMs ?? 30_000;
    this.healthTimeoutMs = cfg.healthTimeoutMs ?? 3_000;
    this.now = cfg.now ?? Date.now;
  }

  get configured(): boolean {
    return Boolean(this.url && this.secret);
  }

  /** Trạng thái agent, cache 30 s (cả kết quả lỗi). null = chưa cấu hình / không kết nối được. */
  async health(force = false): Promise<AgentHealth | null> {
    if (!this.configured) return null;
    const t = this.now();
    if (!force && this.cache && t - this.cache.at < this.healthTtlMs) return this.cache.value;
    let value: AgentHealth | null = null;
    try {
      const res = await fetch(`${this.url}/health`, { signal: AbortSignal.timeout(this.healthTimeoutMs) });
      const body = res.ok ? await res.json() : null;
      value = isHealth(body) ? body : null;
    } catch {
      value = null;
    }
    this.cache = { at: t, value };
    return value;
  }

  async run(body: AgentRunRequest): Promise<AgentRunResponse> {
    if (!this.configured) throw new AgentError("not_configured");
    let res: Response;
    try {
      res = await fetch(`${this.url}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Agent-Secret": this.secret },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(this.runTimeoutMs),
      });
    } catch (e) {
      const name = (e as Error)?.name;
      throw new AgentError(name === "TimeoutError" || name === "AbortError" ? "timeout" : "unreachable");
    }
    let data: unknown;
    try {
      data = await res.json();
    } catch (e) {
      const name = (e as Error)?.name;
      if (name === "TimeoutError" || name === "AbortError") throw new AgentError("timeout");
      throw new AgentError(res.ok ? "invalid_response" : `http_${res.status}`, res.status);
    }
    if (!res.ok) {
      const code = (data as { error?: unknown })?.error;
      throw new AgentError(typeof code === "string" && /^[a-z_]{1,40}$/.test(code) ? code : `http_${res.status}`, res.status);
    }
    if (!isRunResponse(data)) throw new AgentError("invalid_response", res.status);
    return data;
  }
}
