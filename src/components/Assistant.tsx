/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, Loader2, Mic, MicOff, Send, ShoppingCart, SquarePen, X } from "lucide-react";
import { User } from "../types.js";
import { motion, AnimatePresence } from "motion/react";
import { useModalA11y } from "../hooks/useModalA11y.js";
import { useTranslation } from "react-i18next";
import { ProposalCard } from "./assistant/ProposalCard.js";
import { ClarificationChips } from "./assistant/ClarificationChips.js";
import {
  activeOptionsIndex,
  applyErrorKey,
  classifyAgentResponse,
  turnsToMessages,
  type AgentMessage,
  type ProposalView,
  type ServerTurn,
} from "../utils/assistantAgent.js";

interface AssistantProps {
  currentUser: User;
  authHeaders: Record<string, string>;
}

interface AssistantShoppingItem {
  name: string;
  quantity?: string;
  note?: string;
}

interface AssistantAction {
  id: string;
  type: "create_shopping_items";
  title: string;
  items: AssistantShoppingItem[];
  status?: "pending" | "running" | "done" | "error";
  error?: string;
}

/** Tin nhắn agent (kind/options/proposal) hoặc trợ lý cũ (actions). */
interface ChatMessage extends AgentMessage {
  actions?: AssistantAction[];
}

/** unknown = chưa hỏi server; agent = trợ lý nâng cao; legacy = /api/assistant/chat cũ. */
type AssistantMode = "unknown" | "agent" | "legacy";

const NOW_TICK_MS = 30 * 1000;

export function Assistant({ currentUser, authHeaders }: AssistantProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const welcome = useCallback((): ChatMessage => ({
    role: "assistant",
    content: t("assistant.welcome", { name: currentUser.fullName })
  }), [t, currentUser.fullName]);
  const [messages, setMessages] = useState<ChatMessage[]>(() => [welcome()]);
  const [mode, setMode] = useState<AssistantMode>("unknown");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [proposalBusy, setProposalBusy] = useState<Record<string, boolean>>({});
  const [proposalErrors, setProposalErrors] = useState<Record<string, string>>({});
  const [nowMs, setNowMs] = useState(() => Date.now());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  // authHeaders là object mới mỗi lần App render — giữ bản mới nhất qua ref để effect không chạy lại.
  const authRef = useRef(authHeaders);
  authRef.current = authHeaders;
  const welcomeRef = useRef(welcome);
  welcomeRef.current = welcome;
  // Một lượt gửi / đặt lại hội thoại đang chạy — tải lịch sử về muộn không được ghi đè tin nhắn của lượt này.
  const busyRef = useRef(false);
  const proposalBusyRef = useRef(new Set<string>());

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort?.();
      }
    };
  }, []);

  const panelRef = useRef<HTMLDivElement | null>(null);
  const closePanel = useCallback(() => setOpen(false), []);
  useModalA11y(open, closePanel, panelRef);

  const updateAction = (actionId: string, patch: Partial<AssistantAction>) => {
    setMessages(prev => prev.map(msg => {
      if (!msg.actions) return msg;
      return {
        ...msg,
        actions: msg.actions.map(action => action.id === actionId ? { ...action, ...patch } : action)
      };
    }));
  };

  const pushAssistant = (content: string, extra: Partial<ChatMessage> = {}) =>
    setMessages(prev => [...prev, { role: "assistant", content, ...extra }]);

  // Mở trợ lý → tải hội thoại gần nhất (và biết agent có dùng được không).
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setHistoryLoading(true);
    fetch("/api/assistant/conversations/latest", { headers: authRef.current })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (cancelled) return;
        if (!data?.available) {
          setMode("legacy");
          return;
        }
        setMode("agent");
        if (busyRef.current) return;
        const conv = data.conversation as { id: string; turns: ServerTurn[] } | null;
        setConversationId(conv?.id ?? null);
        setMessages([welcomeRef.current(), ...turnsToMessages(conv?.turns ?? [])]);
      })
      .catch(() => { if (!cancelled) setMode(prev => (prev === "agent" ? prev : "legacy")); })
      .finally(() => { if (!cancelled) setHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [open]);

  // Đồng hồ cho nhãn "Đã hết hạn" của card khi khung chat đang mở.
  useEffect(() => {
    if (!open) return;
    setNowMs(Date.now());
    const id = window.setInterval(() => setNowMs(Date.now()), NOW_TICK_MS);
    return () => window.clearInterval(id);
  }, [open]);

  // Cuộn trong khung chat (không dùng scrollIntoView — làm cả trang nhảy trên iOS).
  useEffect(() => {
    const el = scrollRef.current;
    if (open && el) el.scrollTop = el.scrollHeight;
  }, [messages, loading, open]);

  const newConversation = async () => {
    if (busyRef.current) return;
    busyRef.current = true;
    setLoading(true);
    try {
      const res = await fetch("/api/assistant/conversations", { method: "POST", headers: authHeaders });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.conversation) throw new Error(data?.error || t("assistant.errorConnect"));
      setConversationId(data.conversation.id);
      setMessages([welcome()]);
      setProposalErrors({});
    } catch (err: any) {
      pushAssistant(err.message || t("assistant.errorConnect"));
    } finally {
      busyRef.current = false;
      setLoading(false);
    }
  };

  /** Gửi qua agent. true = đã xử lý xong; false = cần rơi về trợ lý cũ. */
  const sendToAgent = async (question: string): Promise<boolean> => {
    const res = await fetch("/api/assistant/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders },
      body: JSON.stringify({ message: question, ...(conversationId ? { conversationId } : {}) })
    });
    const body = await res.json().catch(() => null);
    const outcome = classifyAgentResponse(res.status, body);
    switch (outcome.type) {
      case "ok":
        setConversationId(outcome.data.conversationId);
        pushAssistant(outcome.data.reply || t("assistant.fallbackAnswer"), {
          kind: outcome.data.kind,
          ...(outcome.data.options?.length ? { options: outcome.data.options } : {}),
          ...(outcome.data.proposal ? { proposal: outcome.data.proposal } : {}),
        });
        return true;
      case "fallback":
        setMode("legacy");
        return false;
      case "busy":
        pushAssistant(outcome.message || t("assistant.agent.busy"));
        return true;
      case "reset":
        setConversationId(null);
        pushAssistant(outcome.message || t("assistant.errorConnect"));
        return true;
      default:
        pushAssistant(outcome.message || t("assistant.errorConnect"));
        return true;
    }
  };

  const sendQuestion = async (rawQuestion: string) => {
    const question = rawQuestion.trim();
    if (!question || busyRef.current || historyLoading) return;

    busyRef.current = true;
    setMessages(prev => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      if (mode !== "legacy" && await sendToAgent(question)) return;

      const res = await fetch("/api/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({ message: question })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || t("assistant.errorBusy"));

      setMessages(prev => [...prev, {
        role: "assistant",
        content: data.answer || t("assistant.fallbackAnswer"),
        actions: Array.isArray(data.actions) ? data.actions : []
      }]);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: err.message || t("assistant.errorConnect")
      }]);
    } finally {
      busyRef.current = false;
      setLoading(false);
    }
  };
  // Nhập giọng nói gọi lại sau khi đã render lại → luôn dùng bản sendQuestion mới nhất (mode/conversationId hiện tại).
  const sendRef = useRef(sendQuestion);
  sendRef.current = sendQuestion;

  const ask = (e: React.FormEvent) => {
    e.preventDefault();
    void sendQuestion(input);
  };

  const startVoiceInput = () => {
    const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!Recognition) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: t("assistant.voiceNotSupported")
      }]);
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop?.();
      setIsListening(false);
      return;
    }

    const recognition = new Recognition();
    recognitionRef.current = recognition;
    recognition.lang = "vi-VN";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = (event: any) => {
      setIsListening(false);
      if (event?.error === "aborted") return;
      const message = event?.error === "not-allowed"
        ? t("assistant.voicePermission")
        : t("assistant.voiceNotClear");
      setMessages(prev => [...prev, { role: "assistant", content: message }]);
    };
    recognition.onresult = (event: any) => {
      const transcript = String(event?.results?.[0]?.[0]?.transcript || "").trim();
      if (!transcript) return;
      setInput(transcript);
      void sendRef.current(transcript);
    };

    recognition.start();
  };

  const replaceProposal = (p: ProposalView) =>
    setMessages(prev => prev.map(msg => (msg.proposal?.id === p.id ? { ...msg, proposal: p } : msg)));

  const proposalRequest = async (p: ProposalView, action: "apply" | "cancel") => {
    if (proposalBusyRef.current.has(p.id)) return; // chống bấm 2 lần
    proposalBusyRef.current.add(p.id);
    setProposalBusy(prev => ({ ...prev, [p.id]: true }));
    setProposalErrors(prev => ({ ...prev, [p.id]: "" }));
    try {
      const res = await fetch(`/api/assistant/proposals/${encodeURIComponent(p.id)}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify(action === "apply" ? { planHash: p.planHash } : {})
      });
      const data = await res.json().catch(() => null);
      if (data?.proposal) replaceProposal(data.proposal);
      if (!res.ok) {
        const key = applyErrorKey(res.status, data?.code);
        setProposalErrors(prev => ({ ...prev, [p.id]: key ? t(key) : (data?.error || t("assistant.errorConnect")) }));
      }
    } catch {
      setProposalErrors(prev => ({ ...prev, [p.id]: t("assistant.errorConnect") }));
    } finally {
      proposalBusyRef.current.delete(p.id);
      setProposalBusy(prev => ({ ...prev, [p.id]: false }));
    }
  };

  const optionsIndex = activeOptionsIndex(messages);

  const runAction = async (action: AssistantAction) => {
    if (action.status === "running" || action.status === "done") return;

    updateAction(action.id, { status: "running", error: "" });

    try {
      if (action.type !== "create_shopping_items") {
        throw new Error(t("assistant.actionUnsupported"));
      }

      const items = action.items.filter(item => item.name.trim());
      if (items.length === 0) {
        throw new Error(t("assistant.actionNoItems"));
      }

      for (const item of items) {
        const res = await fetch("/api/shopping", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders },
          body: JSON.stringify({
            name: item.name.trim(),
            quantity: item.quantity?.trim() || "",
            note: item.note?.trim() || t("assistant.actionAddNote")
          })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.error || t("assistant.actionAddError", { name: item.name }));
        }
      }

      updateAction(action.id, { status: "done", error: "" });
      setMessages(prev => [...prev, {
        role: "assistant",
        content: t("assistant.actionAdded", { n: items.length })
      }]);
    } catch (err: any) {
      updateAction(action.id, {
        status: "error",
        error: err.message || t("assistant.actionUnsupported")
      });
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-[calc(1.25rem+env(safe-area-inset-bottom))] right-5 z-30 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-full w-12 h-12 shadow-2xl shadow-sky-500/20 flex items-center justify-center"
        title={t("assistant.title")}
      >
        <Bot className="w-5 h-5" />
      </button>

      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-50 flex items-end justify-end p-4 pt-[calc(1rem+env(safe-area-inset-top))] pb-[calc(1rem+env(safe-area-inset-bottom))] bg-slate-950/60 backdrop-blur-xs">
            <motion.div
              ref={panelRef}
              tabIndex={-1}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              role="dialog"
              aria-modal="true"
              aria-label={t("assistant.dialogAria")}
              className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden outline-none"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <Bot className="w-4 h-4 text-sky-400" />
                  <span className="text-sm font-bold text-slate-100">{t("assistant.title")}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {mode === "agent" && (
                    <button
                      type="button"
                      onClick={() => void newConversation()}
                      disabled={loading}
                      className="flex items-center gap-1 px-2 py-1.5 text-[11px] font-bold text-slate-400 hover:text-slate-100 bg-slate-950 rounded-lg disabled:opacity-60 cursor-pointer"
                      title={t("assistant.agent.newConversation")}
                    >
                      <SquarePen className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">{t("assistant.agent.newConversation")}</span>
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="p-1.5 text-slate-400 hover:text-slate-100 bg-slate-950 rounded-lg cursor-pointer"
                    aria-label={t("common.close")}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div ref={scrollRef} className="h-96 overflow-y-auto p-4 space-y-3">
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`text-xs leading-relaxed rounded-2xl px-3 py-2 max-w-[88%] whitespace-pre-line ${msg.role === "user" ? "ml-auto bg-sky-500 text-slate-950 font-semibold" : "bg-slate-950 neu-pressed-sm text-slate-300"}`}
                  >
                    <div>{msg.content}</div>

                    {msg.proposal && (
                      <div className="mt-3">
                        <ProposalCard
                          proposal={msg.proposal}
                          nowMs={nowMs}
                          busy={!!proposalBusy[msg.proposal.id]}
                          error={proposalErrors[msg.proposal.id]}
                          onApprove={() => void proposalRequest(msg.proposal!, "apply")}
                          onCancel={() => void proposalRequest(msg.proposal!, "cancel")}
                        />
                      </div>
                    )}
                    {msg.kind === "proposal" && !msg.proposal && (
                      <div className="mt-2 text-[11px] text-slate-500 italic">{t("assistant.agent.proposalGone")}</div>
                    )}

                    {idx === optionsIndex && msg.options && (
                      <ClarificationChips options={msg.options} disabled={loading || historyLoading} onPick={(o) => void sendQuestion(o)} />
                    )}

                    {msg.actions && msg.actions.length > 0 && (
                      <div className="mt-3 space-y-2 whitespace-normal">
                        {msg.actions.map(action => (
                          <div key={action.id} className="border border-slate-800 bg-slate-900/80 rounded-xl p-3 space-y-2">
                            <div className="flex items-start gap-2">
                              <ShoppingCart className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                              <div className="min-w-0 flex-1">
                                <p className="font-bold text-slate-100">{action.title}</p>
                                <ul className="mt-1 space-y-0.5 text-[11px] text-slate-400">
                                  {action.items.map((item, itemIndex) => (
                                    <li key={`${action.id}_${itemIndex}`} className="flex gap-1.5">
                                      <span className="text-slate-600">-</span>
                                      <span>
                                        {item.name}
                                        {item.quantity ? <span className="text-slate-500"> ({item.quantity})</span> : null}
                                      </span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            </div>

                            {action.status === "error" && (
                              <div className="flex items-center gap-1.5 text-[11px] text-rose-400">
                                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                                <span>{action.error}</span>
                              </div>
                            )}

                            {action.status === "done" ? (
                              <div className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>{t("assistant.actionDone")}</span>
                              </div>
                            ) : (
                              <button
                                type="button"
                                onClick={() => void runAction(action)}
                                disabled={action.status === "running"}
                                className="w-full flex items-center justify-center gap-1.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-60 text-slate-950 rounded-lg px-3 py-2 text-[11px] font-bold transition-all cursor-pointer"
                              >
                                {action.status === "running" ? (
                                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                ) : (
                                  <ShoppingCart className="w-3.5 h-3.5" />
                                )}
                                {action.status === "running" ? t("assistant.actionAdding") : t("assistant.actionAddBtn", { n: action.items.length })}
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {historyLoading && messages.length <= 1 && (
                  <div className="text-xs text-slate-500">{t("assistant.agent.loadingHistory")}</div>
                )}
                {loading && <div className="text-xs text-slate-500">{t("assistant.thinking")}</div>}
              </div>

              <form onSubmit={ask} className="p-3 border-t border-slate-800 flex gap-2">
                <button
                  type="button"
                  onClick={startVoiceInput}
                  disabled={loading || historyLoading}
                  className={`shrink-0 rounded-xl px-3 py-2 border transition-all cursor-pointer disabled:opacity-60 ${isListening ? "bg-rose-500 text-slate-950 border-rose-400" : "bg-slate-950 text-slate-400 hover:text-slate-100 border-slate-800 hover:bg-slate-800"}`}
                  title={isListening ? t("assistant.voiceStopTitle") : t("assistant.voiceMicTitle")}
                >
                  {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                </button>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={isListening ? t("assistant.inputListening") : t("assistant.inputPlaceholder")}
                  className="flex-1 bg-slate-950 neu-pressed-sm rounded-xl px-3 py-2 text-xs text-slate-200 outline-none focus:border-sky-500 min-w-0"
                />
                <button disabled={loading || historyLoading} type="submit" className="bg-sky-500 hover:bg-sky-400 disabled:opacity-60 text-slate-950 rounded-xl px-3 py-2">
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
