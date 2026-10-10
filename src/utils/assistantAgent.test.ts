/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { describe, it, expect } from "vitest";
import {
  activeOptionsIndex,
  applyErrorKey,
  classifyAgentResponse,
  proposalState,
  resultFor,
  turnsToMessages,
  type ProposalView,
} from "./assistantAgent.js";

const NOW = Date.parse("2026-10-10T10:00:00.000Z");

function proposal(patch: Partial<ProposalView> = {}): ProposalView {
  return {
    id: "p1", planHash: "h", status: "pending", results: null, error: null, uncertain: false,
    preview: [{ icon: "🛒", text: "Thêm 2 món: Sữa, Trứng", tone: "add" }],
    expiresAt: "2026-10-10T10:30:00.000Z", appliedAt: null,
    ...patch,
  };
}

describe("classifyAgentResponse", () => {
  it("200 → ok kèm dữ liệu", () => {
    const body = { conversationId: "c1", kind: "answer", reply: "Chào", options: [] };
    expect(classifyAgentResponse(200, body)).toEqual({ type: "ok", data: body });
  });
  it("503 có fallback → dùng trợ lý cũ", () => {
    expect(classifyAgentResponse(503, { fallback: true, reason: "disabled" })).toEqual({ type: "fallback" });
  });
  it("429 → bận (không fallback), giữ thông điệp server (vd. hết lượt trong giờ)", () => {
    expect(classifyAgentResponse(429, { error: "x" })).toEqual({ type: "busy", message: "x" });
    expect(classifyAgentResponse(429, null)).toEqual({ type: "busy", message: "" });
  });
  it("lỗi khác → error với thông điệp server (nếu có)", () => {
    expect(classifyAgentResponse(400, { error: "Câu hỏi quá dài" }))
      .toEqual({ type: "error", message: "Câu hỏi quá dài" });
    expect(classifyAgentResponse(500, null)).toEqual({ type: "error", message: "" });
  });
  it("200 nhưng body sai dạng (proxy trả HTML/null) → error, không ném", () => {
    expect(classifyAgentResponse(200, null)).toEqual({ type: "error", message: "" });
    expect(classifyAgentResponse(200, { kind: "answer" })).toEqual({ type: "error", message: "" });
  });
  it("hội thoại không còn (404) / bị đặt lại (409) → reset để lượt sau tạo hội thoại mới", () => {
    expect(classifyAgentResponse(404, { error: "Không tìm thấy cuộc trò chuyện." }))
      .toEqual({ type: "reset", message: "Không tìm thấy cuộc trò chuyện." });
    expect(classifyAgentResponse(409, { error: "đặt lại" })).toEqual({ type: "reset", message: "đặt lại" });
  });
  it("503 không có fallback (vd. proxy lỗi) → error, không fallback", () => {
    expect(classifyAgentResponse(503, { error: "x" })).toEqual({ type: "error", message: "x" });
  });
});

describe("proposalState", () => {
  it("pending còn hạn → pending; quá hạn → expired (dù server chưa dọn)", () => {
    expect(proposalState(proposal(), NOW)).toBe("pending");
    expect(proposalState(proposal({ expiresAt: "2026-10-10T09:59:59.000Z" }), NOW)).toBe("expired");
  });
  it("failed do khởi động lại → uncertain; failed khác → failed", () => {
    expect(proposalState(proposal({ status: "failed", uncertain: true }), NOW)).toBe("uncertain");
    expect(proposalState(proposal({ status: "failed", error: "lệch" }), NOW)).toBe("failed");
  });
  it("các trạng thái khác giữ nguyên", () => {
    for (const s of ["applying", "applied", "cancelled", "expired"] as const) {
      expect(proposalState(proposal({ status: s }), NOW)).toBe(s);
    }
  });
});

describe("applyErrorKey", () => {
  it("guard lệch → báo dữ liệu vừa thay đổi", () => {
    expect(applyErrorKey(409, "conflict")).toBe("assistant.agent.conflict");
  });
  it("hết hạn / chưa hỗ trợ / trợ lý tắt / bận có thông điệp riêng", () => {
    expect(applyErrorKey(409, "expired")).toBe("assistant.agent.expiredError");
    expect(applyErrorKey(501, "unsupported")).toBe("assistant.agent.unsupported");
    expect(applyErrorKey(409, "disabled")).toBe("assistant.agent.disabledApply");
    expect(applyErrorKey(429, undefined)).toBe("assistant.agent.busy");
  });
  it("mã khác → null (dùng thông điệp server)", () => {
    expect(applyErrorKey(500, "write_failed")).toBeNull();
    expect(applyErrorKey(404, "not_found")).toBeNull();
  });
});

describe("resultFor", () => {
  const p = proposal({
    status: "applied",
    results: [{ index: 0, ok: true, ids: ["a", "b"] }, { index: 1, ok: true, id: "s1", skipped: true }],
  });
  it("khớp kết quả theo chỉ số dòng preview", () => {
    expect(resultFor(p, 0)).toBe("done");
    expect(resultFor(p, 1)).toBe("skipped");
    expect(resultFor(p, 2)).toBeNull();
  });
  it("chưa áp dụng → null", () => {
    expect(resultFor(proposal(), 0)).toBeNull();
  });
  it("kết quả lỗi → error", () => {
    expect(resultFor(proposal({ status: "applied", results: [{ index: 0, ok: false, error: "x" }] }), 0)).toBe("error");
  });
});

describe("turnsToMessages", () => {
  it("chuyển turn server thành tin nhắn; gắn proposal + options", () => {
    const p = proposal();
    const msgs = turnsToMessages([
      { role: "user", text: "thêm sữa", at: "t1" },
      { role: "assistant", text: "Mình đề xuất:", kind: "proposal", proposalId: "p1", proposal: p, at: "t2" },
      { role: "assistant", text: "Loại nào?", kind: "clarification", options: ["A", "B"], at: "t3" },
      { role: "assistant", text: "Đề xuất đã bị dọn", kind: "proposal", proposalId: "gone", proposal: null, at: "t4" },
    ]);
    expect(msgs).toEqual([
      { role: "user", content: "thêm sữa" },
      { role: "assistant", content: "Mình đề xuất:", kind: "proposal", proposal: p },
      { role: "assistant", content: "Loại nào?", kind: "clarification", options: ["A", "B"] },
      { role: "assistant", content: "Đề xuất đã bị dọn", kind: "proposal" },
    ]);
  });
});

describe("activeOptionsIndex", () => {
  it("chỉ câu hỏi lại cuối cùng (chưa ai trả lời) mới bấm được", () => {
    expect(activeOptionsIndex([
      { role: "assistant", content: "?", kind: "clarification", options: ["A"] },
      { role: "user", content: "A" },
    ])).toBe(-1);
    expect(activeOptionsIndex([
      { role: "user", content: "x" },
      { role: "assistant", content: "?", kind: "clarification", options: ["A"] },
    ])).toBe(1);
    expect(activeOptionsIndex([{ role: "assistant", content: "?", kind: "clarification", options: [] }])).toBe(-1);
    expect(activeOptionsIndex([])).toBe(-1);
  });
});
