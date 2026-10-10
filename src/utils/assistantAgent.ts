/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Logic thuần cho UI trợ lý AI agent (phase 6): phân loại phản hồi, trạng thái card đề xuất,
// chuyển hội thoại server → tin nhắn. Không gọi API, không React — để test được.

export type PreviewTone = "add" | "edit" | "delete";

export interface PreviewLine {
  icon: string;
  text: string;
  tone: PreviewTone;
}

export interface ApplyResultView {
  index: number;
  ok: boolean;
  id?: string;
  ids?: string[];
  skipped?: boolean;
  error?: string;
}

export type ProposalStatus = "pending" | "applying" | "applied" | "cancelled" | "expired" | "failed";

/** Dạng `publicProposal` của server (server/agentRoutes.ts). */
export interface ProposalView {
  id: string;
  planHash: string;
  preview: PreviewLine[];
  status: ProposalStatus;
  results: ApplyResultView[] | null;
  error: string | null;
  uncertain?: boolean;
  expiresAt: string;
  appliedAt: string | null;
}

export type AgentKind = "answer" | "proposal" | "clarification";

export interface ServerTurn {
  role: "user" | "assistant";
  text: string;
  kind?: AgentKind;
  options?: string[];
  proposalId?: string;
  proposal?: ProposalView | null;
  at: string;
}

/** Tin nhắn agent trong khung chat (tin nhắn trợ lý cũ có thêm `actions`). */
export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
  kind?: AgentKind;
  options?: string[];
  proposal?: ProposalView;
}

export interface AgentReply {
  conversationId: string;
  kind: AgentKind;
  reply: string;
  options: string[];
  proposal?: ProposalView;
}

export type AgentResponse =
  | { type: "ok"; data: AgentReply }
  | { type: "fallback" }
  | { type: "busy"; message: string }
  | { type: "reset"; message: string }
  | { type: "error"; message: string };

const errorText = (body: unknown): string => {
  const e = (body as { error?: unknown } | null)?.error;
  return typeof e === "string" ? e : "";
};

/** 503 `{fallback:true}` → trợ lý cũ; 429 → bận; 404/409 → bỏ hội thoại; còn lại là lỗi hiển thị nguyên văn server. */
export function classifyAgentResponse(status: number, body: unknown): AgentResponse {
  if (status >= 200 && status < 300) {
    const b = body as Partial<AgentReply> | null;
    if (!b || typeof b.conversationId !== "string" || typeof b.reply !== "string") return { type: "error", message: "" };
    return { type: "ok", data: body as AgentReply };
  }
  if (status === 503 && (body as { fallback?: unknown } | null)?.fallback === true) return { type: "fallback" };
  if (status === 429) return { type: "busy", message: errorText(body) };
  // Hội thoại đã bị dọn / đặt lại (đổi vai trò): bỏ conversationId để lượt sau tạo hội thoại mới.
  if (status === 404 || status === 409) return { type: "reset", message: errorText(body) };
  return { type: "error", message: errorText(body) };
}

export type ProposalState = Exclude<ProposalStatus, "failed"> | "failed" | "uncertain";

/** Trạng thái hiển thị của card: pending quá hạn coi như hết hạn (server chỉ dọn mỗi 30 phút). */
export function proposalState(p: ProposalView, nowMs: number): ProposalState {
  if (p.status === "pending" && nowMs >= Date.parse(p.expiresAt)) return "expired";
  if (p.status === "failed" && p.uncertain) return "uncertain";
  return p.status;
}

/** Khoá i18n cho lỗi khi Duyệt; null = dùng thông điệp của server. */
export function applyErrorKey(status: number, code: string | undefined): string | null {
  if (status === 429) return "assistant.agent.busy";
  switch (code) {
    case "conflict": return "assistant.agent.conflict";
    case "expired": return "assistant.agent.expiredError";
    case "unsupported": return "assistant.agent.unsupported";
    case "disabled": return "assistant.agent.disabledApply";
    default: return null;
  }
}

/** Kết quả của dòng preview thứ `index` sau khi áp dụng (preview và operation cùng thứ tự). */
export function resultFor(p: ProposalView, index: number): "done" | "skipped" | "error" | null {
  const r = p.results?.find((x) => x.index === index);
  if (!r) return null;
  if (!r.ok) return "error";
  return r.skipped ? "skipped" : "done";
}

export function turnsToMessages(turns: ServerTurn[]): AgentMessage[] {
  return turns.map((t) => {
    const m: AgentMessage = { role: t.role, content: t.text };
    if (t.kind) m.kind = t.kind;
    if (t.options?.length) m.options = t.options;
    if (t.proposal) m.proposal = t.proposal;
    return m;
  });
}

/** Chỉ số tin nhắn có nút chọn nhanh còn bấm được: câu hỏi lại nằm cuối khung chat. */
export function activeOptionsIndex(messages: AgentMessage[]): number {
  const i = messages.length - 1;
  const last = messages[i];
  return last && last.role === "assistant" && last.kind === "clarification" && last.options?.length ? i : -1;
}
