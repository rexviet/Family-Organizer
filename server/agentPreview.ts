/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Dựng các dòng của card "Duyệt" từ operation (spec §9). Do Node dựng — không lấy chữ của
// agent; tên bản ghi bị sửa/xoá lấy từ DB (red-team L4) để card không mâu thuẫn dữ liệu thật.

import type { AgentOperation } from "./agentContract.js";
import vi from "../src/i18n/locales/vi.json";

export interface PreviewLine {
  icon: string;
  text: string;
  tone: "add" | "edit" | "delete";
}

export interface PreviewContext {
  users: { id: string; fullName: string }[];
  shoppingItems: { id: string; name: string; quantity?: string }[];
  tasks: { id: string; title: string; dueDate?: string; assigneeId?: string | null; priority?: string; status?: string; description?: string }[];
  plans: { id: string; title: string; startDate?: string; endDate?: string; description?: string; isShared?: boolean; recurrenceType?: string; recurrenceWeekdays?: number[] }[];
  transactions: { id: string; type: string; amount: number; category: string; date: string; description: string; account?: string }[];
  categoryLabel?: (id: string) => string;
}

const MAX_LISTED_ITEMS = 5;
const MISSING = "(không còn tồn tại)";

const PRIORITY: Record<string, string> = { low: "thấp", medium: "vừa", high: "cao" };
const STATUS: Record<string, string> = { todo: "cần làm", in_progress: "đang làm", completed: "xong" };
const ACCOUNT: Record<string, string> = { cash: "tiền mặt", bank: "ngân hàng", e_wallet: "ví điện tử" };
const RECURRENCE: Record<string, string> = {
  none: "không lặp", daily: "hằng ngày", weekly: "hằng tuần", monthly: "hằng tháng", yearly: "hằng năm",
};
const WEEKDAY = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];

const moneyFmt = new Intl.NumberFormat("vi-VN");
export const money = (n: number) => `${moneyFmt.format(n)}₫`;

/** "YYYY-MM-DD HH:mm" → "HH:mm dd/MM"; "YYYY-MM-DD" → "dd/MM". Chuỗi lạ giữ nguyên. */
export function shortDate(value: string | undefined | null): string {
  if (!value) return "(trống)";
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(value);
  if (!m) return value;
  const day = `${m[3]}/${m[2]}`;
  return m[4] ? `${m[4]}:${m[5]} ${day}` : day;
}

function describeFor(ctx: PreviewContext) {
  const userName = (id: string | null | undefined) =>
    id ? ctx.users.find((u) => u.id === id)?.fullName ?? "(thành viên không còn)" : "(chưa giao)";
  const category = (id: string) => ctx.categoryLabel?.(id) ?? id;

  // Giá trị hiển thị cho một trường trong "cũ → mới".
  const show = (field: string, v: unknown): string => {
    if (v === undefined || v === null || v === "") return field === "assigneeId" ? "(chưa giao)" : "(trống)";
    switch (field) {
      case "dueDate": case "startDate": case "endDate": case "date": return shortDate(String(v));
      case "assigneeId": return userName(String(v));
      case "priority": return PRIORITY[String(v)] ?? String(v);
      case "status": return STATUS[String(v)] ?? String(v);
      case "account": return ACCOUNT[String(v)] ?? String(v);
      case "recurrenceType": return RECURRENCE[String(v)] ?? String(v);
      case "recurrenceWeekdays": return Array.isArray(v) ? v.map((d) => WEEKDAY[d] ?? d).join(", ") : String(v);
      case "isShared": return v ? "cả nhà" : "riêng tư";
      case "amount": return money(Number(v));
      case "category": return category(String(v));
      default: return String(v);
    }
  };
  const LABEL: Record<string, string> = {
    title: "tên", description: "mô tả", dueDate: "hạn", assigneeId: "giao", priority: "ưu tiên", status: "trạng thái",
    startDate: "bắt đầu", endDate: "kết thúc", isShared: "chia sẻ", recurrenceType: "lặp", recurrenceWeekdays: "thứ lặp",
    amount: "số tiền", category: "hạng mục", date: "ngày", account: "tài khoản",
  };
  const diff = (old: Record<string, unknown> | undefined, changes: Record<string, unknown>) =>
    Object.entries(changes)
      .map(([k, v]) => `${LABEL[k] ?? k} ${old ? show(k, old[k]) : "?"} → ${show(k, v)}`)
      .join("; ");

  const item = (id: string) => {
    const it = ctx.shoppingItems.find((i) => i.id === id);
    return it ? (it.quantity ? `${it.name} (${it.quantity})` : it.name) : MISSING;
  };
  const quoted = (rec: { title?: string; description?: string } | undefined, key: "title" | "description") =>
    rec ? `"${rec[key]}"` : MISSING;
  const txKind = (type: string) => (type === "income" ? "khoản thu" : "khoản chi");

  return (op: AgentOperation): PreviewLine => {
    switch (op.type) {
      case "shopping.add": {
        const names = op.items.map((i) => (i.quantity ? `${i.name} (${i.quantity})` : i.name));
        const listed = names.slice(0, MAX_LISTED_ITEMS).join(", ");
        const more = names.length > MAX_LISTED_ITEMS ? ` và ${names.length - MAX_LISTED_ITEMS} món khác` : "";
        return { icon: "🛒", text: `Thêm ${names.length} món: ${listed}${more}`, tone: "add" };
      }
      case "shopping.set_purchased":
        return { icon: "✅", text: `Đánh dấu ${op.purchased ? "đã mua" : "chưa mua"}: ${item(op.itemId)}`, tone: "edit" };
      case "shopping.delete":
        return { icon: "🗑️", text: `Xoá khỏi danh sách đi chợ: ${item(op.itemId)}`, tone: "delete" };

      case "task.create": {
        const parts = [`Tạo việc "${op.title}"`];
        if (op.assigneeId) parts.push(`giao ${userName(op.assigneeId)}`);
        if (op.dueDate) parts.push(shortDate(op.dueDate));
        return { icon: "✅", text: parts.join(" — "), tone: "add" };
      }
      case "task.update": {
        const t = ctx.tasks.find((x) => x.id === op.taskId);
        return { icon: "✏️", text: `Việc ${quoted(t, "title")}: ${diff(t, op.changes)}`, tone: "edit" };
      }
      case "task.delete":
        return { icon: "🗑️", text: `Xoá việc ${quoted(ctx.tasks.find((x) => x.id === op.taskId), "title")}`, tone: "delete" };

      case "plan.create": {
        if (!op.recurrenceType || op.recurrenceType === "none") {
          return { icon: "📅", text: `Tạo sự kiện "${op.title}" — ${shortDate(op.startDate)} → ${shortDate(op.endDate)}`, tone: "add" };
        }
        // Lịch lặp: endDate là "lặp tới" — ghi cả năm để không nhầm với giờ kết thúc trong ngày.
        const days = op.recurrenceWeekdays?.length ? ` (${show("recurrenceWeekdays", op.recurrenceWeekdays)})` : "";
        const until = /^(\d{4})-(\d{2})-(\d{2})/.exec(op.endDate);
        const untilText = until ? ` tới ${until[3]}/${until[2]}/${until[1]}` : "";
        return {
          icon: "📅",
          text: `Tạo sự kiện "${op.title}" — ${shortDate(op.startDate)} · lặp ${show("recurrenceType", op.recurrenceType)}${days}${untilText}`,
          tone: "add",
        };
      }
      case "plan.update": {
        const p = ctx.plans.find((x) => x.id === op.planId);
        return { icon: "✏️", text: `Sự kiện ${quoted(p, "title")}: ${diff(p, op.changes)}`, tone: "edit" };
      }
      case "plan.delete": {
        const p = ctx.plans.find((x) => x.id === op.planId);
        return { icon: "🗑️", text: `Xoá sự kiện ${quoted(p, "title")}${p ? ` — ${shortDate(p.startDate)}` : ""}`, tone: "delete" };
      }

      case "finance.create":
        return {
          icon: op.txType === "income" ? "💰" : "💸",
          text: `Ghi ${txKind(op.txType)} ${money(op.amount)} · ${category(op.category)} · ${shortDate(op.date)}`
            + `${op.account ? ` · ${ACCOUNT[op.account]}` : ""} — ${op.description}`,
          tone: "add",
        };
      case "finance.update": {
        const tx = ctx.transactions.find((x) => x.id === op.txId);
        const head = tx ? `${txKind(tx.type)[0].toUpperCase()}${txKind(tx.type).slice(1)} "${tx.description}"` : `Giao dịch ${MISSING}`;
        return { icon: "✏️", text: `${head}: ${diff(tx, op.changes)}`, tone: "edit" };
      }
      case "finance.delete": {
        const tx = ctx.transactions.find((x) => x.id === op.txId);
        const text = tx
          ? `Xoá ${txKind(tx.type)} ${money(tx.amount)} · ${category(tx.category)} · ${shortDate(tx.date)}`
          : `Xoá giao dịch ${MISSING}`;
        return { icon: "🗑️", text, tone: "delete" };
      }
    }
  };
}

const BUILTIN_LABELS: Record<string, string> = (vi as { categories?: Record<string, string> }).categories ?? {};

/** Nhãn hạng mục cho thẻ Duyệt: mặc định → nhãn tiếng Việt; tự thêm (cc_…) → nhãn gia đình; nguồn thu giữ nguyên. */
export function categoryLabelFrom(custom: { id: string; label: string }[]): (id: string) => string {
  const byId = new Map(custom.map((c) => [c.id, c.label]));
  return (id) => byId.get(id) ?? (Object.hasOwn(BUILTIN_LABELS, id) ? BUILTIN_LABELS[id] : id);
}

/** Mỗi operation một dòng, đúng thứ tự. */
export function buildPreview(operations: AgentOperation[], ctx: PreviewContext): PreviewLine[] {
  return operations.map(describeFor(ctx));
}
