/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Khối "Trợ lý nâng cao" ở Thiết lập (admin): công tắc + trạng thái agent.
// Không hiển thị gì về key/base_url của LLM — chỉ những gì GET /api/settings/agent trả.

import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BrainCircuit, RefreshCw, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

interface AgentStatus {
  enabled: boolean;
  configured: boolean;
  reachable: boolean;
  llmConfigured: boolean;
  model: string | null;
  version: string | null;
  contractVersion: string;
  contractOk: boolean;
}

interface AgentSettingsProps {
  authHeaders: () => Record<string, string>;
}

export function AgentSettings({ authHeaders }: AgentSettingsProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [busy, setBusy] = useState<"" | "load" | "save">("load");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setBusy("load");
    setError("");
    try {
      const res = await fetch("/api/settings/agent", { headers: authHeaders() });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) throw new Error(data?.error || t("assistant.agent.settingsLoadError"));
      setStatus(data);
    } catch (e: any) {
      setError(e?.message || t("assistant.agent.settingsLoadError"));
    } finally {
      setBusy("");
    }
    // authHeaders đọc token hiện tại mỗi lần gọi — không cần làm dependency.
  }, [t]);

  useEffect(() => { void load(); }, [load]);

  const toggle = async () => {
    if (!status || busy) return;
    setBusy("save");
    setError("");
    try {
      const res = await fetch("/api/settings/agent", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !status.enabled })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) throw new Error(data?.error || t("assistant.agent.settingsSaveError"));
      setStatus(data);
    } catch (e: any) {
      setError(e?.message || t("assistant.agent.settingsSaveError"));
    } finally {
      setBusy("");
    }
  };

  const yesNo = (ok: boolean) => (
    <span className={`font-semibold ${ok ? "text-emerald-400" : "text-rose-400"}`}>
      {ok ? t("assistant.agent.settingsYes") : t("assistant.agent.settingsNo")}
    </span>
  );

  return (
    <div className="bg-slate-950 neu-pressed-sm rounded-2xl p-4.5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-violet-400" /> {t("assistant.agent.settingsTitle")}
          </h3>
          <p className="text-[11px] text-slate-500">{t("assistant.agent.settingsDesc")}</p>
        </div>
        {status && (
          <button
            type="button"
            aria-pressed={status.enabled}
            title={t("assistant.agent.settingsToggle")}
            onClick={() => void toggle()}
            disabled={busy !== ""}
            className={`shrink-0 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border cursor-pointer transition-all disabled:opacity-60 ${status.enabled ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" : "bg-slate-900 text-slate-500 border-slate-800"}`}
          >
            {status.enabled ? t("assistant.agent.settingsOn") : t("assistant.agent.settingsOff")}
          </button>
        )}
      </div>

      {status && !status.configured && (
        <p className="text-[11px] text-amber-400 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> {t("assistant.agent.settingsNotConfigured")}
        </p>
      )}

      {status?.configured && (
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[11px]">
          <div className="bg-slate-900 neu-flat rounded-xl px-3 py-2">
            <dt className="text-[10px] text-slate-500">{t("assistant.agent.settingsReachable")}</dt>
            <dd>{yesNo(status.reachable)}</dd>
          </div>
          <div className="bg-slate-900 neu-flat rounded-xl px-3 py-2">
            <dt className="text-[10px] text-slate-500">{t("assistant.agent.settingsLlm")}</dt>
            <dd>{yesNo(status.llmConfigured)}</dd>
          </div>
          <div className="bg-slate-900 neu-flat rounded-xl px-3 py-2">
            <dt className="text-[10px] text-slate-500">{t("assistant.agent.settingsContract")}</dt>
            <dd>{yesNo(status.contractOk)}</dd>
          </div>
          <div className="bg-slate-900 neu-flat rounded-xl px-3 py-2 min-w-0">
            <dt className="text-[10px] text-slate-500">{t("assistant.agent.settingsModel")}</dt>
            <dd className="font-mono text-slate-200 truncate" title={status.model ?? ""}>{status.model || "—"}</dd>
          </div>
          <div className="bg-slate-900 neu-flat rounded-xl px-3 py-2 min-w-0">
            <dt className="text-[10px] text-slate-500">{t("assistant.agent.settingsVersion")}</dt>
            <dd className="font-mono text-slate-200 truncate">{status.version || "—"}</dd>
          </div>
        </dl>
      )}

      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] text-slate-500 flex items-start gap-1.5">
          <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-px text-amber-400" /> {t("assistant.agent.settingsPrivacy")}
        </p>
        <button
          type="button"
          onClick={() => void load()}
          disabled={busy !== ""}
          className="shrink-0 flex items-center gap-1 text-[11px] font-bold text-slate-400 hover:text-slate-100 disabled:opacity-60 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${busy === "load" ? "animate-spin" : ""}`} /> {t("assistant.agent.settingsRefresh")}
        </button>
      </div>

      {error && (
        <p className="text-[11px] text-rose-400 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> {error}
        </p>
      )}
    </div>
  );
}
