/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Lưu hội thoại + đề xuất của trợ lý AI trong data/agent.db — file SQLite RIÊNG, không vào
// FamilyOrganizerDB (sqliteSave ghi lại toàn bộ collection mỗi lần ghi). File này nằm ngoài
// backup/snapshot cập nhật; bản app cũ không biết nó nên "Quay về" vẫn an toàn.

import fs from "fs";
import path from "path";
import crypto from "crypto";
import Database from "better-sqlite3";
import type { AgentOperation } from "./agentContract.js";

const MINUTE = 60 * 1000;
const DAY = 24 * 60 * MINUTE;
export const PROPOSAL_TTL_MS = 30 * MINUTE;
const CONVERSATION_KEEP_MS = 30 * DAY;
const PROPOSAL_KEEP_MS = 7 * DAY;
const MAX_TURNS = 200;

export type ProposalStatus = "pending" | "applying" | "applied" | "cancelled" | "expired" | "failed";

/** Một dòng hiển thị trong khung chat (UI không đọc được history dạng ModelMessage). */
export interface StoredTurn {
  role: "user" | "assistant";
  text: string;
  kind?: "answer" | "proposal" | "clarification";
  options?: string[];
  proposalId?: string;
  at: string;
}

export interface Conversation {
  id: string;
  userId: string;
  messages: unknown[]; // pydantic-ai ModelMessage JSON (agent đã cắt còn 20 lượt)
  turns: StoredTurn[];
  createdAt: string;
  updatedAt: string;
}

export interface ApplyResult {
  index: number;
  ok: boolean;
  id?: string;
  ids?: string[];
  skipped?: boolean;
  error?: string;
}

export interface Proposal {
  id: string;
  conversationId: string;
  userId: string;
  operations: AgentOperation[];
  planHash: string;
  preview: unknown[];
  status: ProposalStatus;
  results: ApplyResult[] | null;
  error: string | null;
  createdAt: string;
  expiresAt: string;
  appliedAt: string | null;
}

export const DEFAULT_AGENT_DB_PATH = path.join(process.cwd(), "data", "agent.db");

const iso = (ms: number) => new Date(ms).toISOString();
const newId = (prefix: string) => `${prefix}_${Date.now()}_${crypto.randomBytes(4).toString("hex")}`;

interface ConversationRow { id: string; user_id: string; messages: string; turns: string; created_at: string; updated_at: string }
interface ProposalRow {
  id: string; conversation_id: string; user_id: string; operations: string; plan_hash: string; preview: string;
  status: ProposalStatus; results: string | null; error: string | null; created_at: string; expires_at: string; applied_at: string | null;
}

function toConversation(r: ConversationRow): Conversation {
  return {
    id: r.id, userId: r.user_id, messages: JSON.parse(r.messages), turns: JSON.parse(r.turns),
    createdAt: r.created_at, updatedAt: r.updated_at,
  };
}

function toProposal(r: ProposalRow): Proposal {
  return {
    id: r.id, conversationId: r.conversation_id, userId: r.user_id, operations: JSON.parse(r.operations),
    planHash: r.plan_hash, preview: JSON.parse(r.preview), status: r.status,
    results: r.results ? JSON.parse(r.results) : null, error: r.error,
    createdAt: r.created_at, expiresAt: r.expires_at, appliedAt: r.applied_at,
  };
}

export class AgentStore {
  private db: Database.Database;

  constructor(file: string = DEFAULT_AGENT_DB_PATH) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    this.db = new Database(file);
    this.db.pragma("journal_mode = WAL");
    this.db.pragma("busy_timeout = 5000");
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS agent_conversations (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, messages TEXT NOT NULL, turns TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_agent_conv_user ON agent_conversations(user_id, updated_at);
      CREATE TABLE IF NOT EXISTS agent_proposals (
        id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, user_id TEXT NOT NULL, operations TEXT NOT NULL,
        plan_hash TEXT NOT NULL, preview TEXT NOT NULL, status TEXT NOT NULL, results TEXT, error TEXT,
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL, applied_at TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_agent_prop_conv ON agent_proposals(conversation_id);
      CREATE INDEX IF NOT EXISTS idx_agent_prop_user ON agent_proposals(user_id, status);
    `);
  }

  close(): void {
    this.db.close();
  }

  // --- Hội thoại ---

  createConversation(userId: string, now = Date.now()): Conversation {
    const c: Conversation = { id: newId("conv"), userId, messages: [], turns: [], createdAt: iso(now), updatedAt: iso(now) };
    this.db.prepare(
      "INSERT INTO agent_conversations (id, user_id, messages, turns, created_at, updated_at) VALUES (?, ?, '[]', '[]', ?, ?)",
    ).run(c.id, userId, c.createdAt, c.updatedAt);
    return c;
  }

  getConversation(id: string): Conversation | undefined {
    const r = this.db.prepare("SELECT * FROM agent_conversations WHERE id = ?").get(id) as ConversationRow | undefined;
    return r ? toConversation(r) : undefined;
  }

  latestConversation(userId: string): Conversation | undefined {
    const r = this.db.prepare(
      "SELECT * FROM agent_conversations WHERE user_id = ? ORDER BY updated_at DESC, rowid DESC LIMIT 1",
    ).get(userId) as ConversationRow | undefined;
    return r ? toConversation(r) : undefined;
  }

  saveConversation(id: string, messages: unknown[], turns: StoredTurn[], now = Date.now()): void {
    this.db.prepare("UPDATE agent_conversations SET messages = ?, turns = ?, updated_at = ? WHERE id = ?")
      .run(JSON.stringify(messages), JSON.stringify(turns.slice(-MAX_TURNS)), iso(now), id);
  }

  // --- Đề xuất ---

  createProposal(
    input: { conversationId: string; userId: string; operations: AgentOperation[]; planHash: string; preview: unknown[] },
    now = Date.now(),
  ): Proposal {
    const p: Proposal = {
      id: newId("prop"), ...input, status: "pending", results: null, error: null,
      createdAt: iso(now), expiresAt: iso(now + PROPOSAL_TTL_MS), appliedAt: null,
    };
    this.db.prepare(
      `INSERT INTO agent_proposals (id, conversation_id, user_id, operations, plan_hash, preview, status, created_at, expires_at)
       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)`,
    ).run(p.id, p.conversationId, p.userId, JSON.stringify(p.operations), p.planHash, JSON.stringify(p.preview), p.createdAt, p.expiresAt);
    return p;
  }

  getProposal(id: string): Proposal | undefined {
    const r = this.db.prepare("SELECT * FROM agent_proposals WHERE id = ?").get(id) as ProposalRow | undefined;
    return r ? toProposal(r) : undefined;
  }

  listProposals(conversationId: string): Proposal[] {
    return (this.db.prepare("SELECT * FROM agent_proposals WHERE conversation_id = ? ORDER BY created_at")
      .all(conversationId) as ProposalRow[]).map(toProposal);
  }

  /** pending → applying có điều kiện. true = lượt này giành được quyền ghi (chỉ một lượt thắng). */
  beginApply(id: string): boolean {
    return this.db.prepare("UPDATE agent_proposals SET status = 'applying' WHERE id = ? AND status = 'pending'").run(id).changes === 1;
  }

  finishApply(id: string, status: "applied" | "failed", results: ApplyResult[], now = Date.now(), error?: string): void {
    this.db.prepare(
      "UPDATE agent_proposals SET status = ?, results = ?, error = ?, applied_at = ? WHERE id = ? AND status = 'applying'",
    ).run(status, JSON.stringify(results), error ?? null, status === "applied" ? iso(now) : null, id);
  }

  /** Đánh dấu một proposal pending là thất bại/hết hạn mà không qua applying (vd. guard lệch). */
  markPending(id: string, status: "failed" | "expired", error?: string): void {
    this.db.prepare("UPDATE agent_proposals SET status = ?, error = ? WHERE id = ? AND status = 'pending'")
      .run(status, error ?? null, id);
  }

  cancel(id: string, userId: string): boolean {
    return this.db.prepare(
      "UPDATE agent_proposals SET status = 'cancelled' WHERE id = ? AND user_id = ? AND status = 'pending'",
    ).run(id, userId).changes === 1;
  }

  /** Gọi lúc app khởi động: lượt apply bị cắt ngang không chạy lại — người dùng tự kiểm tra. */
  failStaleApplying(_now = Date.now()): number {
    return this.db.prepare(
      "UPDATE agent_proposals SET status = 'failed', error = ? WHERE status = 'applying'",
    ).run("Ứng dụng khởi động lại khi đang áp dụng đề xuất — hãy kiểm tra lại dữ liệu trước khi hỏi lại trợ lý.").changes;
  }

  cleanup(now = Date.now()): { conversations: number; proposals: number; expired: number } {
    const expired = this.db.prepare("UPDATE agent_proposals SET status = 'expired' WHERE status = 'pending' AND expires_at <= ?")
      .run(iso(now)).changes;
    const conversations = this.db.prepare("DELETE FROM agent_conversations WHERE updated_at < ?")
      .run(iso(now - CONVERSATION_KEEP_MS)).changes;
    const proposals = this.db.prepare("DELETE FROM agent_proposals WHERE created_at < ? AND status != 'applying'")
      .run(iso(now - PROPOSAL_KEEP_MS)).changes;
    return { conversations, proposals, expired };
  }

  /** Đổi vai trò / xoá người dùng (M5): bỏ hội thoại + đề xuất còn chờ của họ. */
  deleteUserData(userId: string): void {
    this.db.transaction(() => {
      this.db.prepare("DELETE FROM agent_conversations WHERE user_id = ?").run(userId);
      this.db.prepare("DELETE FROM agent_proposals WHERE user_id = ? AND status = 'pending'").run(userId);
    })();
  }
}
