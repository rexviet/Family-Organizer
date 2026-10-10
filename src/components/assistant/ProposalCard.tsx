/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Card "Duyệt" cho đề xuất của trợ lý AI agent. Props thuần — không gọi API.
// Chỉ render dữ liệu server dựng (preview là chuỗi thuần, không render HTML từ model).

import React from "react";
import { AlertTriangle, Check, CheckCircle2, Clock, Loader2, Minus, ShieldCheck, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { proposalState, resultFor, type PreviewLine, type ProposalView } from "../../utils/assistantAgent.js";

interface ProposalCardProps {
  proposal: ProposalView;
  nowMs: number;
  busy: boolean;
  error?: string;
  onApprove: () => void;
  onCancel: () => void;
}

const TONE_CLASS: Record<PreviewLine["tone"], string> = {
  add: "text-slate-200",
  edit: "text-slate-200",
  delete: "text-rose-400",
};

/** Dòng sửa: tô "cũ → mới" — phần cũ gạch mờ, mũi tên màu nhấn. */
function LineText({ line }: { line: PreviewLine }) {
  if (line.tone !== "edit" || !line.text.includes(" → ")) return <>{line.text}</>;
  const parts = line.text.split(" → ");
  return (
    <>
      {parts.map((part, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span className="text-sky-400 font-bold"> → </span>}
          <span className={i < parts.length - 1 ? "text-slate-400" : undefined}>{part}</span>
        </React.Fragment>
      ))}
    </>
  );
}

export function ProposalCard({ proposal, nowMs, busy, error, onApprove, onCancel }: ProposalCardProps) {
  const { t } = useTranslation();
  const state = proposalState(proposal, nowMs);
  const dimmed = state === "expired" || state === "cancelled";

  const badge = (() => {
    switch (state) {
      case "applied":
        return { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", icon: <CheckCircle2 className="w-3 h-3" />, label: t("assistant.agent.statusApplied") };
      case "applying":
        return { cls: "bg-sky-500/10 text-sky-400 border-sky-500/20", icon: <Loader2 className="w-3 h-3 animate-spin" />, label: t("assistant.agent.statusApplying") };
      case "cancelled":
        return { cls: "bg-slate-800 text-slate-400 border-slate-850", icon: <X className="w-3 h-3" />, label: t("assistant.agent.statusCancelled") };
      case "expired":
        return { cls: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: <Clock className="w-3 h-3" />, label: t("assistant.agent.statusExpired") };
      case "failed":
        return { cls: "bg-rose-500/10 text-rose-400 border-rose-500/20", icon: <AlertTriangle className="w-3 h-3" />, label: t("assistant.agent.statusFailed") };
      case "uncertain":
        return { cls: "bg-amber-500/10 text-amber-400 border-amber-500/20", icon: <AlertTriangle className="w-3 h-3" />, label: t("assistant.agent.statusUncertain") };
      default:
        return null;
    }
  })();

  // Lỗi lúc bấm (đã dịch) ưu tiên hơn lý do server lưu cho proposal thất bại.
  const shownError = error || (state === "failed" || state === "uncertain" ? proposal.error ?? "" : "");

  return (
    <div className={`border border-slate-800 bg-slate-900/80 rounded-xl p-3 space-y-2 whitespace-normal transition-opacity ${dimmed ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <p className="flex items-center gap-1.5 font-bold text-slate-100 whitespace-nowrap">
          <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
          {t("assistant.agent.proposalTitle")}
        </p>
        {badge && (
          <span className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-lg border font-semibold ${badge.cls}`}>
            {badge.icon}
            {badge.label}
          </span>
        )}
      </div>

      <ul className="space-y-1.5 text-[11px]">
        {proposal.preview.map((line, i) => {
          const result = resultFor(proposal, i);
          return (
            <li
              key={i}
              className={`flex items-start gap-2 rounded-lg px-2 py-1.5 ${line.tone === "delete" ? "bg-rose-500/10" : "bg-slate-950/40"}`}
            >
              <span className="shrink-0 leading-snug" aria-hidden>{line.icon}</span>
              <span className={`min-w-0 flex-1 leading-snug break-words ${TONE_CLASS[line.tone]}`}>
                <LineText line={line} />
              </span>
              {result === "done" && (
                <span className="shrink-0 inline-flex items-center gap-0.5 text-[10px] font-semibold text-emerald-400">
                  <Check className="w-3 h-3" />{t("assistant.agent.resultDone")}
                </span>
              )}
              {result === "skipped" && (
                <span className="shrink-0 inline-flex items-center gap-0.5 text-[10px] font-semibold text-slate-500">
                  <Minus className="w-3 h-3" />{t("assistant.agent.resultSkipped")}
                </span>
              )}
              {result === "error" && (
                <span className="shrink-0 inline-flex items-center gap-0.5 text-[10px] font-semibold text-rose-400">
                  <X className="w-3 h-3" />{t("assistant.agent.resultError")}
                </span>
              )}
            </li>
          );
        })}
      </ul>

      {shownError && (
        <div className="flex items-start gap-1.5 text-[11px] text-rose-400">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
          <span>{shownError}</span>
        </div>
      )}

      {state === "pending" && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onApprove}
            disabled={busy}
            className="flex-1 flex items-center justify-center gap-1.5 bg-indigo-500 hover:bg-indigo-400 disabled:opacity-60 text-white rounded-xl px-3 py-2 text-[11px] font-bold cursor-pointer disabled:cursor-default"
          >
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            {busy ? t("assistant.agent.approving") : t("assistant.agent.approve")}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="flex items-center justify-center gap-1.5 bg-slate-800 hover:text-slate-100 disabled:opacity-60 text-slate-300 rounded-xl px-3 py-2 text-[11px] font-bold cursor-pointer disabled:cursor-default"
          >
            <X className="w-3.5 h-3.5" />
            {t("assistant.agent.cancel")}
          </button>
        </div>
      )}
    </div>
  );
}
