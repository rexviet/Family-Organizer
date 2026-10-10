/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// Hợp đồng operation giữa agent (Python) và Node — bản cài phía Node.
// Nguồn chân lý: agent/contracts/operations.schema.json (+ README.md cùng thư mục).
// Bản Python cài độc lập và phải ra cùng chuỗi trên agent/contracts/vectors.json.

import { createHash } from "crypto";
import schemaJson from "../agent/contracts/operations.schema.json";

// ---------------------------------------------------------------------------
// Kiểu operation (khớp $defs trong schema — đổi một bên thì đổi cả hai)
// ---------------------------------------------------------------------------

type BaseUpdatedAt = { updatedAt: string };
type BaseFingerprint = { fingerprint: string };
type Priority = "low" | "medium" | "high";
type PlanRecurrence = "none" | "daily" | "weekly" | "monthly" | "yearly";
type Account = "cash" | "bank" | "e_wallet";

export type AgentOperation =
  | { type: "shopping.add"; items: { name: string; quantity?: string; note?: string }[] }
  | { type: "shopping.set_purchased"; itemId: string; purchased: boolean; base: BaseUpdatedAt }
  | { type: "shopping.delete"; itemId: string; base: BaseUpdatedAt }
  | {
      type: "task.create"; title: string; description?: string; dueDate?: string;
      assigneeId?: string | null; priority?: Priority; rewardPoints?: number; isShared?: boolean;
    }
  | {
      type: "task.update"; taskId: string; base: BaseUpdatedAt;
      changes: {
        title?: string; description?: string; dueDate?: string; assigneeId?: string | null;
        priority?: Priority; status?: "todo" | "in_progress";
      };
    }
  | { type: "task.delete"; taskId: string; base: BaseUpdatedAt }
  | {
      type: "plan.create"; title: string; description?: string; startDate: string; endDate: string;
      isShared?: boolean; recurrenceType?: PlanRecurrence; recurrenceWeekdays?: number[];
    }
  | {
      type: "plan.update"; planId: string; base: BaseFingerprint;
      changes: {
        title?: string; description?: string; startDate?: string; endDate?: string;
        isShared?: boolean; recurrenceType?: PlanRecurrence; recurrenceWeekdays?: number[];
      };
    }
  | { type: "plan.delete"; planId: string; base: BaseFingerprint }
  | {
      type: "finance.create"; txType: "income" | "expense"; amount: number; category: string;
      date: string; description: string; account?: Account;
    }
  | {
      type: "finance.update"; txId: string; base: BaseFingerprint;
      changes: { amount?: number; category?: string; date?: string; description?: string; account?: Account };
    }
  | { type: "finance.delete"; txId: string; base: BaseFingerprint };

export type AgentOperationType = AgentOperation["type"];

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- schema là JSON tuỳ ý
type Schema = Record<string, any>;
const schema = schemaJson as Schema;

export const CONTRACT_VERSION: number = schema.contractVersion;
const LIMITS: { maxOperations: number; maxShoppingAddItemsTotal: number } = schema.limits;

// ---------------------------------------------------------------------------
// Canonical JSON + hash
// ---------------------------------------------------------------------------

const LONE_SURROGATE = /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;

function canonicalString(s: string, path: string): string {
  if (LONE_SURROGATE.test(s)) throw new Error(`${path}: chuỗi có surrogate lẻ`);
  // JSON.stringify của chuỗi hợp lệ chỉ escape " \ và ký tự < U+0020 (dạng \n, \t… hoặc
  // \u00xx chữ thường) — đúng quy tắc trong README, trùng json.dumps(ensure_ascii=False).
  return JSON.stringify(s);
}

/** So sánh theo code point (sort mặc định của JS so theo UTF-16 code unit). */
function compareCodePoints(a: string, b: string): number {
  const ia = a[Symbol.iterator]();
  const ib = b[Symbol.iterator]();
  for (;;) {
    const x = ia.next();
    const y = ib.next();
    if (x.done || y.done) return (x.done ? 0 : 1) - (y.done ? 0 : 1);
    const d = x.value.codePointAt(0)! - y.value.codePointAt(0)!;
    if (d !== 0) return d;
  }
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const proto = Object.getPrototypeOf(v);
  return proto === Object.prototype || proto === null;
}

function canonicalAt(value: unknown, path: string): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) throw new Error(`${path}: chỉ chấp nhận số nguyên an toàn`);
    return String(value === 0 ? 0 : value); // -0 → "0"
  }
  if (typeof value === "string") return canonicalString(value, path);
  if (Array.isArray(value)) {
    return "[" + value.map((v, i) => {
      if (v === undefined) throw new Error(`${path}[${i}]: undefined trong mảng`);
      return canonicalAt(v, `${path}[${i}]`);
    }).join(",") + "]";
  }
  if (isPlainObject(value)) {
    const keys = Object.keys(value).filter((k) => value[k] !== undefined).sort(compareCodePoints);
    return "{" + keys.map((k) =>
      canonicalString(k, path) + ":" + canonicalAt(value[k], `${path}.${k}`),
    ).join(",") + "}";
  }
  throw new Error(`${path}: kiểu không hỗ trợ (${typeof value})`);
}

/** JSON chuẩn hoá: key sắp theo code point, không khoảng trắng, chỉ số nguyên. Ném lỗi nếu vi phạm. */
export function canonical(value: unknown): string {
  return canonicalAt(value, "$");
}

function sha256hex(text: string): string {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

/** planHash = sha256hex(canonical(operations)). */
export function planHash(operations: unknown): string {
  return sha256hex(canonical(operations));
}

export const FINGERPRINT_FIELDS = {
  transaction: ["amount", "category", "date", "description", "account", "type"],
  plan: [
    "title", "description", "startDate", "endDate", "isShared",
    "isRecurring", "recurrenceType", "recurrenceWeekdays", "color",
  ],
} as const;

export type FingerprintKind = keyof typeof FINGERPRINT_FIELDS;

/** Dấu vân tay cho bản ghi không có `updatedAt`; trường thiếu tính là null. */
export function fingerprint(kind: FingerprintKind, record: object): string {
  const fields = FINGERPRINT_FIELDS[kind];
  if (!fields) throw new Error(`loại bản ghi không hỗ trợ: ${String(kind)}`);
  const rec = record as Record<string, unknown>;
  const picked: Record<string, unknown> = {};
  for (const f of fields) picked[f] = rec[f] === undefined ? null : rec[f];
  return sha256hex(canonical(picked));
}

// ---------------------------------------------------------------------------
// Validator — bộ con JSON Schema 2020-12 mà operations.schema.json dùng
// ---------------------------------------------------------------------------

export interface ContractError { path: string; message: string }

const MAX_ERRORS = 50;

const ANNOTATIONS = new Set(["$schema", "$id", "$defs", "title", "description", "contractVersion", "limits"]);
const KEYWORDS = new Set([
  "$ref", "type", "const", "enum", "pattern", "minLength", "maxLength", "minimum", "maximum",
  "minItems", "maxItems", "uniqueItems", "items", "properties", "required",
  "additionalProperties", "minProperties", "oneOf",
]);

function resolveRef(ref: string): Schema {
  const prefix = "#/$defs/";
  const def = ref.startsWith(prefix) ? schema.$defs?.[ref.slice(prefix.length)] : undefined;
  if (!def) throw new Error(`schema: không tìm thấy ${ref}`);
  return def;
}

// Chặn schema dùng từ khoá mà validator này không hiểu (nếu không sẽ bị bỏ qua âm thầm).
function assertSupported(s: Schema, at: string): void {
  for (const [k, v] of Object.entries(s)) {
    if (ANNOTATIONS.has(k)) continue;
    if (!KEYWORDS.has(k)) throw new Error(`schema ${at}: từ khoá chưa hỗ trợ "${k}"`);
    if (k === "additionalProperties" && v !== false) throw new Error(`schema ${at}: additionalProperties chỉ hỗ trợ false`);
  }
  if (s.$ref) resolveRef(s.$ref);
  if (s.items) assertSupported(s.items, `${at}/items`);
  for (const [k, sub] of Object.entries(s.properties ?? {})) assertSupported(sub as Schema, `${at}/properties/${k}`);
  (s.oneOf ?? []).forEach((sub: Schema, i: number) => assertSupported(sub, `${at}/oneOf/${i}`));
}
assertSupported(schema, "#");
for (const [k, def] of Object.entries(schema.$defs ?? {})) assertSupported(def as Schema, `#/$defs/${k}`);

function typeOf(v: unknown): string {
  if (v === null) return "null";
  if (Array.isArray(v)) return "array";
  if (typeof v === "number") return Number.isSafeInteger(v) ? "integer" : "number";
  if (typeof v === "object") return isPlainObject(v) ? "object" : "other";
  return typeof v;
}

function sameJson(a: unknown, b: unknown): boolean {
  try { return canonical(a) === canonical(b); } catch { return false; }
}

const regexCache = new Map<string, RegExp>();
function regex(p: string): RegExp {
  let r = regexCache.get(p);
  if (!r) { r = new RegExp(p, "u"); regexCache.set(p, r); }
  return r;
}

// Trường hợp đầu vào lớn/độc: đủ lỗi thì dừng, mảng/chuỗi quá dài thì không quét tiếp.
function check(s: Schema, v: unknown, path: string, out: ContractError[]): void {
  if (out.length >= MAX_ERRORS) return;
  if (s.$ref) { check(resolveRef(s.$ref), v, path, out); return; }

  if (s.type !== undefined) {
    const allowed: string[] = Array.isArray(s.type) ? s.type : [s.type];
    const t = typeOf(v);
    if (!allowed.includes(t)) {
      out.push({ path, message: `phải là ${allowed.join("|")}, nhận ${t}` });
      return;
    }
  }
  if ("const" in s && !sameJson(v, s.const)) out.push({ path, message: `phải bằng ${JSON.stringify(s.const)}` });
  if (s.enum && !s.enum.some((e: unknown) => sameJson(v, e))) {
    out.push({ path, message: `phải là một trong ${s.enum.join(", ")}` });
  }

  if (typeof v === "string") {
    // JSON Schema đếm theo code point; số code point ≤ số code unit nên chuỗi quá dài cắt sớm.
    const len = s.maxLength !== undefined && v.length > 2 * s.maxLength ? v.length : [...v].length;
    if (s.minLength !== undefined && len < s.minLength) out.push({ path, message: `ít nhất ${s.minLength} ký tự` });
    if (s.maxLength !== undefined && len > s.maxLength) { out.push({ path, message: `tối đa ${s.maxLength} ký tự` }); return; }
    if (s.pattern !== undefined && !regex(s.pattern).test(v)) out.push({ path, message: `sai định dạng (${s.pattern})` });
  }

  if (typeof v === "number") {
    if (s.minimum !== undefined && v < s.minimum) out.push({ path, message: `phải ≥ ${s.minimum}` });
    if (s.maximum !== undefined && v > s.maximum) out.push({ path, message: `phải ≤ ${s.maximum}` });
  }

  if (Array.isArray(v)) {
    if (s.minItems !== undefined && v.length < s.minItems) out.push({ path, message: `ít nhất ${s.minItems} phần tử` });
    if (s.maxItems !== undefined && v.length > s.maxItems) { out.push({ path, message: `tối đa ${s.maxItems} phần tử` }); return; }
    if (s.uniqueItems && v.some((x, i) => v.findIndex((y) => sameJson(x, y)) !== i)) {
      out.push({ path, message: "phần tử bị trùng" });
    }
    if (s.items) v.forEach((x, i) => check(s.items, x, `${path}[${i}]`, out));
  }

  if (isPlainObject(v)) {
    const props: Schema = s.properties ?? {};
    for (const k of s.required ?? []) {
      if (!Object.hasOwn(v, k)) out.push({ path: `${path}.${k}`, message: "thiếu trường bắt buộc" });
    }
    if (s.minProperties !== undefined && Object.keys(v).length < s.minProperties) {
      out.push({ path, message: `cần ít nhất ${s.minProperties} trường` });
    }
    for (const [k, x] of Object.entries(v)) {
      // Object.hasOwn, không dùng `in`: `in` dò cả prototype nên "constructor", "__proto__"…
      // sẽ lọt qua additionalProperties: false.
      if (Object.hasOwn(props, k)) check(props[k], x, `${path}.${k}`, out);
      else if (s.additionalProperties === false) out.push({ path: `${path}.${k}`, message: "trường không được phép" });
    }
  }

  if (s.oneOf) checkOneOf(s.oneOf, v, path, out);
}

// Union phân biệt bằng `type`: chọn đúng nhánh theo const để báo lỗi gọn; không có
// `type` dạng chuỗi thì quay về luật oneOf chuẩn (khớp đúng một nhánh).
function checkOneOf(branches: Schema[], v: unknown, path: string, out: ContractError[]): void {
  const resolved = branches.map((b) => (b.$ref ? resolveRef(b.$ref) : b));
  if (isPlainObject(v) && typeof v.type === "string") {
    const i = resolved.findIndex((b) => b.properties?.type?.const === v.type);
    if (i < 0) { out.push({ path: `${path}.type`, message: `operation không hỗ trợ: ${v.type}` }); return; }
    check(resolved[i], v, path, out);
    return;
  }
  const matches = resolved.filter((b) => { const e: ContractError[] = []; check(b, v, path, e); return e.length === 0; });
  if (matches.length !== 1) out.push({ path, message: "không khớp đúng một loại operation" });
}

export type ValidationResult =
  | { ok: true; operations: AgentOperation[]; errors: ContractError[] }
  | { ok: false; errors: ContractError[] };

/** Kiểm danh sách operation theo schema + giới hạn ngoài schema. Mọi thứ ngoài hợp đồng bị từ chối. */
export function validateOperations(input: unknown): ValidationResult {
  const errors: ContractError[] = [];
  check(schema, input, "$", errors);
  // Bản sao chỉ gồm dữ liệu JSON (không prototype, không tham chiếu tới đầu vào) — người gọi
  // lưu/hash/apply đúng thứ đã kiểm. canonical ném lỗi (vd. surrogate lẻ) = đầu vào không hợp lệ.
  let copy: AgentOperation[] = [];
  if (errors.length === 0) {
    try {
      copy = JSON.parse(canonical(input));
    } catch (e) {
      errors.push({ path: "$", message: (e as Error).message });
    }
  }
  if (errors.length === 0) {
    const ops = copy;
    const total = ops.reduce((n, op) => n + (op.type === "shopping.add" ? op.items.length : 0), 0);
    if (total > LIMITS.maxShoppingAddItemsTotal) {
      errors.push({ path: "$", message: `tổng số món đi chợ tối đa ${LIMITS.maxShoppingAddItemsTotal}, nhận ${total}` });
    }
  }
  return errors.length === 0
    ? { ok: true, operations: copy, errors: [] }
    : { ok: false, errors: errors.slice(0, MAX_ERRORS) };
}
