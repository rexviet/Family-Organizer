/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Route của trợ lý AI agent (spec §4, §9–11). Tách khỏi server.ts để test được với
// phụ thuộc giả; server.ts chỉ việc nối FamilyDB, agentStore, agentClient vào đây.

import express, { type Request, type Response, type RequestHandler } from "express";
import { CONTRACT_VERSION, planHash, validateOperations } from "./agentContract.js";
import { AgentError, type AgentClient, type AgentHealth } from "./agentClient.js";
import type { AgentTokens } from "./agentToken.js";
import type { AgentStore, Conversation, Proposal, StoredTurn } from "./agentStore.js";
import { buildPreview, type PreviewContext } from "./agentPreview.js";
import { applyProposal, ENABLED_OPERATIONS, type ApplyDeps } from "./agentApply.js";
import { UserRole } from "../src/types.js";

interface Session {
  userId: string;
  username: string;
  fullName: string;
  role: UserRole;
}

export interface AgentRouteDeps {
  store: AgentStore;
  client: Pick<AgentClient, "configured" | "health" | "run">;
  tokens: AgentTokens;
  /** Middleware đặt req.userSession (của app) hoặc trả 401. */
  requireAuth: RequestHandler;
  isEnabled: () => boolean;
  setEnabled: (enabled: boolean) => void;
  /** Dữ liệu cho preview, ĐÃ lọc theo quyền xem của người hỏi (canSeeTask/canSeePlan/thu chi). */
  previewContext: (viewer: { id: string; role: UserRole }) => PreviewContext;
  applyDeps: Omit<ApplyDeps, "store" | "now">;
  broadcast: (event: string, data?: Record<string, unknown>) => void;
  now?: () => number;
  rateLimit?: { max: number; windowMs: number };
}

const MAX_MESSAGE_CHARS = 4000; // khớp RunRequest.message của agent
const TIMEZONE = "Asia/Ho_Chi_Minh";
const WEEKDAYS = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];

type Unavailable = "disabled" | "not_configured" | "unreachable" | "llm_not_configured" | "contract_mismatch";

const FALLBACK_MSG: Record<Unavailable | "run_failed", string> = {
  disabled: "Trợ lý nâng cao đang tắt.",
  not_configured: "Trợ lý nâng cao chưa được cấu hình.",
  unreachable: "Không kết nối được trợ lý nâng cao.",
  llm_not_configured: "Trợ lý nâng cao chưa cấu hình mô hình AI.",
  contract_mismatch: "Phiên bản trợ lý nâng cao không khớp với ứng dụng.",
  run_failed: "Trợ lý nâng cao đang gặp lỗi.",
};

/** Ngày + thứ theo giờ Việt Nam (agent không tự lấy giờ). */
export function vnToday(nowMs: number): { today: string; weekday: string } {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date(nowMs));
  const [y, m, d] = parts.split("-").map(Number);
  return { today: parts, weekday: WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()] };
}

export function publicProposal(p: Proposal) {
  return {
    id: p.id, planHash: p.planHash, preview: p.preview, status: p.status, results: p.results,
    error: p.error, expiresAt: p.expiresAt, appliedAt: p.appliedAt,
  };
}

// Express 4 không bắt lỗi của handler async: không bọc thì request treo và Node sập vì
// unhandled rejection. Lỗi bất ngờ → 500 JSON (không lộ chi tiết).
function safe(fn: (req: Request, res: Response) => unknown): RequestHandler {
  return (req, res) => {
    Promise.resolve()
      .then(() => fn(req, res))
      .catch((e) => {
        console.error(`Lỗi route trợ lý ${req.method} ${req.path}:`, (e as Error)?.message);
        if (!res.headersSent) res.status(500).json({ error: "Trợ lý gặp lỗi, vui lòng thử lại." });
      });
  };
}

export function createAgentRouter(deps: AgentRouteDeps): express.Router {
  const router = express.Router();
  const now = deps.now ?? Date.now;
  const limit = deps.rateLimit ?? { max: 20, windowMs: 60 * 60 * 1000 };
  const turnsByUser = new Map<string, number[]>(); // userId → thời điểm các lượt trong cửa sổ
  const inflight = new Set<string>();
  const { store } = deps;

  const sessionOf = (req: Request) => (req as Request & { userSession: Session }).userSession;

  const requireAdmin: RequestHandler = (req, res, next) => {
    if (sessionOf(req)?.role !== UserRole.ADMIN) {
      res.status(403).json({ error: "Chỉ quản trị viên được thực hiện thao tác này!" });
      return;
    }
    next();
  };

  async function availability(force = false): Promise<{ ok: true; health: AgentHealth } | { ok: false; reason: Unavailable; health: AgentHealth | null }> {
    if (!deps.isEnabled()) return { ok: false, reason: "disabled", health: null };
    if (!deps.client.configured) return { ok: false, reason: "not_configured", health: null };
    const health = await deps.client.health(force);
    if (!health || !health.ok) return { ok: false, reason: "unreachable", health };
    if (!health.llmConfigured) return { ok: false, reason: "llm_not_configured", health };
    if (health.contractVersion !== CONTRACT_VERSION) return { ok: false, reason: "contract_mismatch", health };
    return { ok: true, health };
  }

  function takeRateSlot(userId: string): boolean {
    const t = now();
    const recent = (turnsByUser.get(userId) ?? []).filter((x) => t - x < limit.windowMs);
    if (recent.length >= limit.max) {
      turnsByUser.set(userId, recent);
      return false;
    }
    recent.push(t);
    turnsByUser.set(userId, recent);
    return true;
  }

  function conversationView(c: Conversation) {
    const proposals = new Map(store.listProposals(c.id).map((p) => [p.id, publicProposal(p)]));
    return {
      id: c.id, createdAt: c.createdAt, updatedAt: c.updatedAt,
      turns: c.turns.map((t) => (t.proposalId ? { ...t, proposal: proposals.get(t.proposalId) ?? null } : t)),
    };
  }

  function logTurn(entry: Record<string, unknown>) {
    // Không log nội dung hội thoại / token.
    console.log(JSON.stringify({ event: "agent_turn", ...entry }));
  }

  // --- Lượt trò chuyện ---
  router.post("/api/assistant/agent", deps.requireAuth, safe(async (req: Request, res: Response) => {
    const session = sessionOf(req);
    const message = typeof req.body?.message === "string" ? req.body.message.trim() : "";
    if (!message || message.length > MAX_MESSAGE_CHARS) {
      res.status(400).json({ error: `Câu hỏi phải từ 1 đến ${MAX_MESSAGE_CHARS} ký tự.` });
      return;
    }
    const conversationId = req.body?.conversationId;
    if (conversationId !== undefined && conversationId !== null && typeof conversationId !== "string") {
      res.status(400).json({ error: "conversationId không hợp lệ." });
      return;
    }

    const avail = await availability();
    if (avail.ok === false) {
      res.status(503).json({ fallback: true, reason: avail.reason, error: FALLBACK_MSG[avail.reason] });
      return;
    }

    let conv: Conversation | undefined;
    if (conversationId) {
      conv = store.getConversation(conversationId);
      if (!conv || conv.userId !== session.userId) {
        res.status(404).json({ error: "Không tìm thấy cuộc trò chuyện." });
        return;
      }
    }

    if (inflight.has(session.userId)) {
      res.status(429).json({ error: "Trợ lý đang trả lời câu trước của bạn, chờ chút nhé." });
      return;
    }
    if (!takeRateSlot(session.userId)) {
      res.status(429).json({ error: `Bạn đã hỏi ${limit.max} lượt trong một giờ — nghỉ chút rồi hỏi tiếp nhé.` });
      return;
    }

    inflight.add(session.userId);
    const started = now();
    const agentToken = deps.tokens.issue(session.userId);
    try {
      conv = conv ?? store.latestConversation(session.userId) ?? store.createConversation(session.userId, started);
      const { today, weekday } = vnToday(started);
      let result;
      try {
        result = await deps.client.run({
          message,
          history: conv.messages,
          user: { id: session.userId, fullName: session.fullName, role: session.role },
          agentToken,
          today,
          weekday,
        });
      } catch (e) {
        const code = e instanceof AgentError ? e.code : "unknown";
        logTurn({ userId: session.userId, status: "error", error: code, ms: now() - started });
        if (code === "busy") {
          res.status(429).json({ error: "Trợ lý đang bận với người khác, thử lại sau ít giây nhé." });
        } else {
          res.status(503).json({ fallback: true, reason: "run_failed", error: FALLBACK_MSG.run_failed });
        }
        return;
      }
      if (result.contractVersion !== CONTRACT_VERSION) {
        logTurn({ userId: session.userId, status: "error", error: "contract_mismatch", ms: now() - started });
        res.status(503).json({ fallback: true, reason: "contract_mismatch", error: FALLBACK_MSG.contract_mismatch });
        return;
      }

      // Hội thoại bị xoá trong lúc agent chạy (đổi vai trò / xoá người dùng) → bỏ lượt này.
      if (!store.getConversation(conv.id)) {
        logTurn({ userId: session.userId, status: "conversation_gone", ms: now() - started });
        res.status(409).json({ error: "Cuộc trò chuyện đã được đặt lại — hãy hỏi lại nhé." });
        return;
      }

      let kind = result.kind;
      let reply = result.reply;
      let proposal: Proposal | undefined;
      if (kind === "proposal") {
        const checked = validateOperations(result.operations);
        // Chỉ lưu/dựng preview cho loại đã bật ghi: preview của loại khác sẽ đọc bản ghi
        // (việc, thu chi…) mà người hỏi có thể không được xem.
        const enabledOnly = checked.ok && checked.operations.every((op) => ENABLED_OPERATIONS.has(op.type));
        if (checked.ok && enabledOnly) {
          const operations = checked.operations;
          proposal = store.createProposal({
            conversationId: conv.id, userId: session.userId, operations, planHash: planHash(operations),
            preview: buildPreview(operations, deps.previewContext({ id: session.userId, role: session.role })),
          }, now());
        } else {
          kind = "answer";
          reply = checked.ok
            ? "Trợ lý hiện chỉ thay đổi được danh sách đi chợ. Việc, lịch và thu chi bạn sửa trực tiếp trong app nhé."
            : "Mình chưa tạo được đề xuất hợp lệ cho yêu cầu này. Bạn nói lại cụ thể hơn giúp mình nhé.";
          logTurn({ userId: session.userId, status: checked.ok ? "unsupported_proposal" : "invalid_proposal" });
        }
      }
      const options = kind === "clarification" ? (result.options ?? []) : [];
      const at = new Date(now()).toISOString();
      const turns: StoredTurn[] = [
        ...conv.turns,
        { role: "user", text: message, at: new Date(started).toISOString() },
        {
          role: "assistant", text: reply, kind, at,
          ...(options.length ? { options } : {}),
          ...(proposal ? { proposalId: proposal.id } : {}),
        },
      ];
      store.saveConversation(conv.id, result.history, turns, now());
      logTurn({ userId: session.userId, role: session.role, status: "ok", kind, usage: result.usage ?? null, ms: now() - started });
      res.json({
        conversationId: conv.id, kind, reply, options,
        ...(proposal ? { proposal: publicProposal(proposal) } : {}),
      });
    } finally {
      deps.tokens.revoke(agentToken);
      inflight.delete(session.userId);
    }
  }));

  // --- Hội thoại (chỉ của chính mình) ---
  router.get("/api/assistant/conversations/latest", deps.requireAuth, safe(async (req: Request, res: Response) => {
    const session = sessionOf(req);
    const avail = await availability();
    const conv = store.latestConversation(session.userId);
    res.json({ available: avail.ok, ...(avail.ok === false ? { reason: avail.reason } : {}), conversation: conv ? conversationView(conv) : null });
  }));

  router.post("/api/assistant/conversations", deps.requireAuth, safe((req: Request, res: Response) => {
    const userId = sessionOf(req).userId;
    const latest = store.latestConversation(userId);
    // Bấm "mới" liên tục không sinh hàng loạt hội thoại trống.
    const conv = latest && latest.turns.length === 0 ? latest : store.createConversation(userId, now());
    res.json({ conversation: conversationView(conv) });
  }));

  // --- Duyệt / huỷ đề xuất ---
  router.post("/api/assistant/proposals/:id/apply", deps.requireAuth, safe((req: Request, res: Response) => {
    const session = sessionOf(req);
    if (!deps.isEnabled()) {
      res.status(409).json({ error: "Trợ lý nâng cao đang tắt nên không áp dụng được đề xuất.", code: "disabled" });
      return;
    }
    const outcome = applyProposal({ ...deps.applyDeps, store, now }, req.params.id, req.body?.planHash, session);
    if (outcome.ok === true) {
      for (const event of outcome.modules) deps.broadcast(event, { source: "assistant" });
      res.json({ proposal: publicProposal(outcome.proposal) });
      return;
    }
    if (outcome.ok === false) res.status(outcome.status).json({
      error: outcome.error, code: outcome.code,
      ...(outcome.proposal ? { proposal: publicProposal(outcome.proposal) } : {}),
    });
  }));

  router.post("/api/assistant/proposals/:id/cancel", deps.requireAuth, safe((req: Request, res: Response) => {
    const session = sessionOf(req);
    const p = store.getProposal(req.params.id);
    if (!p || p.userId !== session.userId) {
      res.status(404).json({ error: "Không tìm thấy đề xuất." });
      return;
    }
    if (!store.cancel(p.id, session.userId)) {
      res.status(409).json({ error: "Đề xuất không còn chờ duyệt.", code: p.status, proposal: publicProposal(p) });
      return;
    }
    res.json({ proposal: publicProposal(store.getProposal(p.id)!) });
  }));

  // --- Thiết lập (admin) ---
  async function settingsView() {
    const health = deps.client.configured ? await deps.client.health(true) : null;
    return {
      enabled: deps.isEnabled(),
      configured: deps.client.configured,
      reachable: Boolean(health?.ok),
      llmConfigured: Boolean(health?.llmConfigured),
      model: health?.model ?? null,
      version: health?.version ?? null,
      contractVersion: CONTRACT_VERSION,
      contractOk: health ? health.contractVersion === CONTRACT_VERSION : false,
    };
  }

  router.get("/api/settings/agent", deps.requireAuth, requireAdmin, safe(async (_req: Request, res: Response) => {
    res.json(await settingsView());
  }));

  router.post("/api/settings/agent", deps.requireAuth, requireAdmin, safe(async (req: Request, res: Response) => {
    if (typeof req.body?.enabled !== "boolean") {
      res.status(400).json({ error: "Cần gửi { enabled: true | false }." });
      return;
    }
    deps.setEnabled(req.body.enabled);
    deps.broadcast("SETTINGS_UPDATE");
    res.json(await settingsView());
  }));

  return router;
}
