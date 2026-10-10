# Hợp đồng operation Node ↔ Agent

Một nguồn chân lý cho mọi operation mà agent (Python) đề xuất và Node kiểm/ghi
(spec: [docs/ai-agent-spec.md](../../docs/ai-agent-spec.md) §4, §6.2, §9).

| File | Vai trò |
| :--- | :--- |
| `operations.schema.json` | JSON Schema 2020-12 cho **mảng operation của một proposal** + `contractVersion` + `limits` |
| `vectors.json` | Bộ vector chung: `canonical`, `planHash`, `fingerprint`, `invalid` |
| `gen_vectors.py` | Bản cài tham chiếu Python (chỉ stdlib) — tính lại hash trong `vectors.json`; `--check` để CI so |

Bản cài:
- Node: [`server/agentContract.ts`](../../server/agentContract.ts) — `canonical`, `planHash`, `fingerprint`, `validateOperations`, `CONTRACT_VERSION`.
- Python (phase 3): `agent/src/family_agent/contract.py` — **phải pass toàn bộ `vectors.json`**, kể cả mục `invalid`.

## Operation (12 loại, `contractVersion` 1)

Mỗi operation là object có `type` phân biệt; **mọi trường lạ đều bị từ chối** (`additionalProperties: false`
ở mọi cấp, kể cả `items[]`, `changes`, `base`).

| `type` | Trường | `base` |
| :--- | :--- | :--- |
| `shopping.add` | `items: [{name, quantity?, note?}]` (1–20) | — |
| `shopping.set_purchased` | `itemId, purchased` — **đặt** giá trị, không lật | `{updatedAt}` |
| `shopping.delete` | `itemId` | `{updatedAt}` |
| `task.create` | `title, description?, dueDate?, assigneeId?, priority?, rewardPoints?, isShared?` | — |
| `task.update` | `taskId, changes:{title?, description?, dueDate?, assigneeId?, priority?, status?}` | `{updatedAt}` |
| `task.delete` | `taskId` | `{updatedAt}` |
| `plan.create` | `title, description?, startDate, endDate, isShared?, recurrenceType?, recurrenceWeekdays?` | — |
| `plan.update` | `planId, changes:{title?, description?, startDate?, endDate?, isShared?, recurrenceType?, recurrenceWeekdays?}` | `{fingerprint}` |
| `plan.delete` | `planId` | `{fingerprint}` |
| `finance.create` | `txType, amount, category, date, description, account?` | — |
| `finance.update` | `txId, changes:{amount?, category?, date?, description?, account?}` | `{fingerprint}` |
| `finance.delete` | `txId` | `{fingerprint}` |

Ghi chú:
- `task.update.changes.status` chỉ `todo | in_progress`. **Không** có `completed`: hoàn thành qua `saveTask`
  cộng điểm không qua duyệt — tương đương duyệt việc của trẻ, agent không được làm. Không sửa `rewardPoints`.
- `finance.create` dùng `txType` (`income | expense`) vì `type` đã là khoá phân biệt operation.
- `assigneeId: null` = bỏ giao người. `changes` phải có ít nhất 1 trường.
- `FamilyPlan` và `FinancialTransaction` không có `updatedAt` → dùng `fingerprint`.
- Định dạng: `date` = `YYYY-MM-DD`; `startDate/endDate` = `YYYY-MM-DD HH:mm`; `dueDate` = một trong hai.
  Pattern chỉ dùng `[0-9]` (không dùng `\d` — `re` của Python khớp cả chữ số Unicode).
- `amount` là số nguyên đồng, 1 … 10^12. `recurrenceWeekdays`: 0 = Chủ nhật … 6, không trùng.

## Giới hạn (`limits` trong schema)

- Tối đa **10 operation** / proposal (cũng là `maxItems` của schema).
- Tổng số món của mọi `shopping.add` trong một proposal ≤ **30** — JSON Schema không diễn đạt được, validator
  hai bên **phải tự kiểm** (vector `invalid` có `rule` đánh dấu ca này).

## JSON chuẩn hoá (canonical)

Ra **cùng một chuỗi byte** ở Python và Node:

1. Kiểu cho phép: `null`, `true/false`, chuỗi, **số nguyên** trong ±(2^53−1), mảng, object. Số thực, NaN,
   Infinity, số ngoài khoảng → **lỗi** (không làm tròn). Python: `bool` không tính là số; `float` bị từ chối
   kể cả `1.0`.
2. Object: key sắp theo **code point Unicode** (= `sort_keys=True` của Python). Node bỏ key có giá trị `undefined`.
3. Không khoảng trắng: `,` và `:` không có dấu cách.
4. Chuỗi: escape **tối thiểu** — `"` → `\"`, `\` → `\\`, `\b \f \n \r \t`, ký tự khác < U+0020 → `\u00xx`
   (hex chữ thường). Mọi ký tự còn lại (tiếng Việt, emoji, `/`, U+007F, U+2028…) giữ nguyên.
   Chuỗi chứa surrogate lẻ → lỗi. **Không** chuẩn hoá Unicode (NFC/NFD) — hash theo đúng byte nhận được.
5. Mã hoá UTF-8.

Python tương đương: `json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))` sau khi
đã kiểm kiểu như bước 1.

- `planHash = sha256hex(canonical(operations))` — hex chữ thường, 64 ký tự. Thứ tự operation có nghĩa.
- `fingerprint(kind, record) = sha256hex(canonical(pick(record, FIELDS[kind])))`; trường thiếu tính là `null`,
  trường ngoài FIELDS bỏ qua:
  - `transaction`: `amount, category, date, description, account, type`
  - `plan`: `title, description, startDate, endDate, isShared, isRecurring, recurrenceType, recurrenceWeekdays, color`

## Ghi chú cho người cài

- **Validator trả bản sao.** Node (`validateOperations`) trả `operations` dựng lại từ canonical JSON — lưu, hash và
  apply đúng bản sao đó, không dùng lại đầu vào gốc. Chỉ xét key **riêng** của object (`Object.hasOwn`), nên
  `__proto__`, `constructor`… bị coi là trường lạ. Lỗi trả về tối đa 50; mảng/chuỗi vượt giới hạn dừng kiểm sớm.
- **Python (phase 3):**
  - Pattern dùng `re.fullmatch` (hoặc thư viện `jsonschema`, nhưng `$` của `re` khớp trước `\n` cuối chuỗi —
    phải tự chặn; vector `invalid` có ca `"2026-10-09\n"`).
  - Số nguyên phải là `int` thật trước khi tính canonical (Pydantic ép `1.0` → `1`); `jsonschema` coi `1.0` là
    integer nên đừng chỉ dựa vào nó.
  - Pass cả mục `invalid` (kể cả giới hạn 30 món kiểm ngoài schema).
- **Node khi apply (phase 5/9):** schema chỉ kiểm *định dạng* — ngày có thật, `endDate ≥ startDate`, id/thành viên/
  hạng mục còn tồn tại phải kiểm lúc dry-run. Giao dịch cũ có `amount` không nguyên làm `fingerprint` ném lỗi →
  coi như không đề xuất/không apply được bản ghi đó (báo người dùng), không làm tròn.

## Phiên bản & quy tắc đổi hợp đồng

- `contractVersion` (số nguyên) nằm trong schema. Agent trả nó ở `/health` và `/run`; Node từ chối khi lệch
  và quay về assistant cũ.
- **Không bao giờ sửa nghĩa trường cũ.** Thêm operation/trường mới, đổi giới hạn, đổi quy tắc canonical hay
  FIELDS của fingerprint → **tăng `contractVersion`**, cập nhật cả hai bản cài và `vectors.json` trong cùng
  một thay đổi.
- Dữ liệu cũ (proposal đã lưu) có thể còn version trước — Node chỉ apply proposal cùng version hiện tại.

## Cập nhật vector

```sh
python3 agent/contracts/gen_vectors.py          # sửa đầu vào trong vectors.json rồi tính lại hash
python3 agent/contracts/gen_vectors.py --check  # CI chạy lệnh này
npx vitest run server/agentContract.test.ts     # Node phải ra đúng các hash đó
```
