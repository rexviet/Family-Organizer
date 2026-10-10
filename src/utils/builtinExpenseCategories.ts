/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Hạng mục CHI mặc định — file THUẦN (không import i18n/React) để cả giao diện lẫn server (kiểm hạng mục khi
// trợ lý ghi thu chi) dùng chung. Nhãn dịch qua i18n "categories.<value>" ở expenseCategories.ts.

export interface BuiltinCat {
  /** key i18n & giá trị lưu trong transaction.category */
  value: string;
  emoji: string;
  color: string;
}

// Hạng mục CHI mặc định do lập trình viên web app cung cấp — KHÔNG xóa được, chỉ
// có thể ẩn. Thứ tự này cũng là thứ tự hiển thị trong ô chọn. Emoji/màu khớp với
// bộ cũ đã dùng ở Finance (CAT_BAR/categoryIcon) và Dashboard (EXPENSE_CAT_STYLE).
export const BUILTIN_EXPENSE_CATEGORIES: BuiltinCat[] = [
  { value: "food",          emoji: "🍲",  color: "orange" },
  { value: "education2",    emoji: "📚",  color: "violet" },
  { value: "utilities",     emoji: "⚡",  color: "amber" },
  { value: "shopping",      emoji: "🛍️",  color: "pink" },
  { value: "medical",       emoji: "💊",  color: "rose" },
  { value: "transport",     emoji: "🚗",  color: "sky" },
  { value: "debt_bank",     emoji: "🏦",  color: "red" },
  { value: "debt_personal", emoji: "🤝",  color: "teal" },
  { value: "funeral",       emoji: "🌸",  color: "zinc" },
  { value: "ceremony",      emoji: "🎁",  color: "yellow" },
  { value: "other",         emoji: "🏷️",  color: "slate" },
];

/** Key của hạng mục chi mặc định (giá trị lưu trong transaction.category). */
export const BUILTIN_EXPENSE_CATEGORY_KEYS: readonly string[] = BUILTIN_EXPENSE_CATEGORIES.map((c) => c.value);
