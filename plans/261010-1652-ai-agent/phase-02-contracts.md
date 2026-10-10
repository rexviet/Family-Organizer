# Phase 2 — Hợp đồng operation + planHash

**Priority:** P1 · **Effort:** 4h · **Status:** Done (2026-10-10)

## Context Links
- Spec §4, §6.2, §9
- PTC: `contracts/GUARD-HASH.md` — hai bản cài độc lập (Python + TS) cùng một test vector

## Overview
Một nguồn chân lý cho mọi operation mà agent (Python) sinh ra và Node kiểm/ghi. Có nó thì phase 3–4 và 5 làm song song được.

## Key Insights
- `planHash` phải ra **cùng chuỗi** ở Python và Node → định nghĩa JSON chuẩn hoá cụ thể, không dựa vào `json.dumps` mặc định.
- Union có `type` phân biệt; trường lạ bị **loại bỏ (reject)**, không lặng lẽ bỏ qua.

## Requirements
- `agent/contracts/operations.schema.json` (JSON Schema 2020-12): đủ 12 operation của spec §6.2 ngay từ đầu (để M2/M3 không đổi hợp đồng), mỗi cái `additionalProperties: false`.
  - `shopping.add {items:[{name, quantity?, note?}] (1..20)}`
  - `shopping.set_purchased {itemId, purchased, base:{updatedAt}}` (ĐẶT giá trị, không lật — `toggleShoppingItem` lật trạng thái, `db.ts:2199`)
  - `shopping.delete {itemId, base:{updatedAt}}` (`ShoppingItem` có `updatedAt`)
  - `task.create {title, description?, dueDate?, assigneeId?, priority?, rewardPoints?, isShared?}`
  - `task.update {taskId, changes:{title?, description?, dueDate?, assigneeId?, priority?, status?: "todo"|"in_progress"}, base:{updatedAt}}` — **không** cho `completed`: `saveTask` hoàn thành + cộng điểm không qua duyệt (`db.ts:778-795`), tương đương `/approve` mà agent không được có
  - `task.delete {taskId, base:{updatedAt}}`
  - `plan.create {title, description?, startDate, endDate, isShared?, recurrenceType?, recurrenceWeekdays?}`
  - `plan.update {planId, changes:{…}, base:{fingerprint}}` · `plan.delete {planId, base:{fingerprint}}` — `FamilyPlan` **không có** `updatedAt` (`types.ts:156-169`)
  - `finance.create {type, amount(int>0), category, date, description, account?}`
  - `finance.update {txId, changes:{amount?, category?, date?, description?, account?}, base:{fingerprint}}` · `finance.delete {txId, base:{fingerprint}}`
- **Canonical JSON:** key sắp xếp, không khoảng trắng, UTF-8, số nguyên thuần; `planHash = sha256hex(canonical(operations))`.
- **Fingerprint** (bản ghi không có `updatedAt`): `sha256hex(canonical(pick(record, FIELDS)))`, FIELDS cố định theo loại (transaction: `amount,category,date,description,account,type`; plan: `title,description,startDate,endDate,isShared,isRecurring,recurrenceType,recurrenceWeekdays,color`).
- `contractVersion` (số nguyên, bắt đầu `1`) trong schema; agent trả ở `/health` và `/run`, Node từ chối khi lệch → fallback assistant cũ.
- Giới hạn: tổng số món `shopping.add` trong một proposal ≤ 30.
- `agent/contracts/vectors.json`: ≥ 8 cặp `{operations, planHash}` + `{record, fingerprint}`, có tiếng Việt có dấu.

## Related Code Files
- Tạo: `agent/contracts/operations.schema.json`, `agent/contracts/vectors.json`, `agent/contracts/README.md`
- Tạo: `server/agentContract.ts` (canonical, planHash, fingerprint, validate bằng schema — viết validator tay nhỏ hoặc dùng `ajv` nếu đã có trong deps; **kiểm tra trước**, không thêm thư viện nếu tránh được)
- Tạo: `server/agentContract.test.ts`
- (Python bản tương ứng nằm ở phase 3: `agent/src/family_agent/contract.py`)

## Implementation Steps (TDD)
1. Viết `vectors.json` bằng tay + tính hash bằng một script độc lập (`python -c`), ghi kết quả.
2. RED: `agentContract.test.ts` đọc vectors, kỳ vọng `planHash`/`fingerprint` khớp; kỳ vọng reject trường lạ / `amount` âm / `type` lạ.
3. GREEN: cài `canonical`, `planHash`, `fingerprint`, `validateOperations`.
4. README hợp đồng: quy tắc đổi hợp đồng = thêm `version`, không sửa nghĩa trường cũ.

## Todo
- [x] Schema 12 operation
- [x] Vectors + script tính độc lập (`agent/contracts/gen_vectors.py`, CI chạy `--check`)
- [x] `server/agentContract.ts` + test xanh
- [x] README hợp đồng

## Quyết định khi cài (--auto)
- `finance.create` dùng `txType` (`income|expense`) cho loại giao dịch — `type` đã là khoá phân biệt operation.
- Không có `ajv` trong deps → validator tay (bộ con JSON Schema 2020-12) đọc **chính** `operations.schema.json`; gặp từ khoá chưa hỗ trợ thì ném lỗi lúc nạp module (không bỏ qua âm thầm). Lỗi theo đường dẫn `$[i].field`; `type` lạ báo một lỗi gọn.
- `contractVersion` và `limits` (`maxOperations: 10`, `maxShoppingAddItemsTotal: 30`) là từ khoá chú thích trong schema; giới hạn 30 món kiểm ngoài schema.
- Canonical: chỉ số nguyên an toàn (số thực → lỗi), key theo code point, chuỗi có surrogate lẻ → lỗi, không chuẩn hoá Unicode. Fingerprint: trường thiếu = `null`.
- Ràng buộc độ dài/định dạng thêm (id ≤ 100, tiêu đề 1–200, `amount` 1…10^12, pattern ngày chỉ `[0-9]`, `rewardPoints` 0–1000).
- Vectors có thêm mục `canonical` (escape, sắp key) và `invalid` (25 ca) để bản Python kiểm cả validator.
- Dockerfile copy `agent/contracts/` để bundle server khi phase 5 import schema.

- Code review (6.5/10 lần đầu) bắt lỗi **critical**: `k in props` dò prototype → `constructor`/`__proto__` lọt qua `additionalProperties: false`. Đã sửa: `Object.hasOwn`, validator trả **bản sao** dựng từ canonical, chạy canonical trong validate (surrogate lẻ bị từ chối), dừng sớm khi vượt `maxItems`/`maxLength`, tối đa 50 lỗi; thêm vector tương ứng.

## Success Criteria
`npm test` xanh với vectors; tài liệu đủ để phía Python cài lại độc lập.

## Security Considerations
Validator là lớp chặn đầu tiên ở Node cho dữ liệu từ agent — mọi thứ ngoài schema bị từ chối trước khi lưu proposal.

## Next Steps
Phase 3–4 (Python) và 5 (Node) song song.
