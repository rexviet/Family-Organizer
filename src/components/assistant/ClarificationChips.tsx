/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Nút chọn nhanh khi trợ lý hỏi lại: bấm = gửi đúng chuỗi đó như một tin nhắn. Props thuần.

import React from "react";
import { useTranslation } from "react-i18next";

interface ClarificationChipsProps {
  options: string[];
  disabled: boolean;
  onPick: (option: string) => void;
}

export function ClarificationChips({ options, disabled, onPick }: ClarificationChipsProps) {
  const { t } = useTranslation();
  if (options.length === 0) return null;
  return (
    <div role="group" aria-label={t("assistant.agent.pickOption")} className="mt-2 flex flex-wrap gap-1.5 whitespace-normal">
      {options.map((option, i) => (
        <button
          key={`${i}_${option}`}
          type="button"
          onClick={() => onPick(option)}
          disabled={disabled}
          className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 hover:bg-sky-500/20 disabled:opacity-60 cursor-pointer disabled:cursor-default focus:outline-none focus:ring-2 focus:ring-sky-500/40 text-left"
        >
          {option}
        </button>
      ))}
    </div>
  );
}
