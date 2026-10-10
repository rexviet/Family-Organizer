# Phase 9 — Ghi Thu chi + eval đầy đủ (M3)

**Priority:** P2 · **Effort:** 6h · **Status:** Code done (+ đợt sửa sau eval `8bb4a81`) — eval model thật đợt 1 xong (74–84%); đo lại đầy đủ với code cuối bị chặn (router hết hạn mức tháng, 402); đã phát hành trong **v1.2.0** (gộp M1–M3, fork rexviet, 2026-10-11)

## Context Links
- Spec §6.2 (Thu chi), §12
- `server.ts`: `POST/DELETE /api/finance` (admin/member), `GET /api/finance/categories`
- `src/types.ts`: `FinancialTransaction` (không có `updatedAt` → fingerprint)
- PTC: `tests/eval/` (tách khỏi CI, chạy bằng đường dẫn)

## Overview
Bật 3 operation thu chi (rủi ro cao nhất — sai số tiền) và dựng bộ eval chạy với từng model.

## Requirements
- Agent: `propose_create_transaction`, `propose_update_transaction`, `propose_delete_transaction`.
  - `amount` số nguyên VND > 0; hiểu "250k", "1tr2", "1,5 triệu" bằng hàm parse **trong tool** (có test), không để model tự tính.
  - `category` phải thuộc `list_expense_categories` (cả hạng mục tự thêm); không rõ → `ask_user`.
  - `date` mặc định hôm nay; `base.fingerprint` từ bản ghi.
- Node: `canWriteFinance` (admin/member); apply qua `applyBatch`, update **phải merge** `{...oldTx, ...changes}` — `saveTransaction` thay nguyên bản ghi, trường thiếu về mặc định (`amount||0`, `account||"bank"`) và **xoá file ảnh hoá đơn** khi thiếu `receiptImage` (`db.ts:1274-1290`); guard fingerprint. Test: sửa số tiền → hoá đơn vẫn còn, các trường khác giữ nguyên.
- Preview luôn hiện **số tiền đầy đủ** `250.000₫`, loại Thu/Chi, hạng mục, ngày; sửa hiện `cũ → mới`; xoá màu đỏ.
- **Eval** `agent/tests/eval/` (không nằm trong `testpaths`):
  - `cases.yaml` ~50 câu (đọc, ghi 4 module, câu nối, mơ hồ, câu vượt quyền khi đăng nhập role con).
  - Chấm tự động: với câu ghi → so operations kỳ vọng (bỏ qua thứ tự/trường tuỳ chọn); câu đọc → so số liệu chính trong câu trả lời (regex số) hoặc LLM-judge tuỳ chọn; câu mơ hồ → phải ra `clarification`.
  - Dữ liệu fixture: DB mẫu + server Node chạy cổng tạm (hoặc mock API từ fixture JSON).
  - Kết quả ghi `reports/eval-<model>-<date>.md`; README agent cập nhật bảng model đã kiểm chứng.
- Quyết định gỡ `/api/assistant/chat`: chỉ khi eval ≥ 85% và đã chạy ≥ 1 bản phát hành — ghi lại trong CHANGELOG bản gỡ.

## Related Code Files
- Tạo: `agent/src/family_agent/harness/tools/finance.py`, `harness/money.py` + test; `agent/tests/eval/{cases.yaml, run_eval.py, fixtures/}`
- Sửa: `server/permissions.ts`, `server/agentApply.ts`, `server/agentPreview.ts` + test; CHANGELOG `1.4.0`

## Implementation Steps (TDD)
1. `money.py` parse + test (≥ 15 cách viết tiền tiếng Việt).
2. Tool thu chi + test; apply/preview + test (con → 403, fingerprint lệch → 409).
3. Eval harness + chạy với ≥ 2 model; ghi báo cáo.
4. Phát hành M3 (hỏi trước khi push tag).

## Todo
- [x] parse tiền — `harness/money.py` (`parse_vnd`), 70 ca test (≥ 30 cách viết đúng + các ca nhập nhằng phải từ chối)
- [x] 3 tool thu chi — `tools/finance.py` (+ `records.resolve` thêm `name_key`), ví dụ trong instructions
- [x] apply + preview thu chi — `canWriteFinance`, mutator dùng chung `dataMutations.ts`, merge khi sửa, guard fingerprint, xoá file hoá đơn sau khi ghi; nhãn hạng mục trên thẻ Duyệt
- [x] khung eval 57 câu + báo cáo — `agent/eval/{run_eval.py, cases.json, fixtures/app.json}`; [báo cáo](./reports/phase-09-eval.md)
- [x] chạy eval với ≥ 2 model × ≥ 2 lần — 2026-10-10 qua router local ([báo cáo](./reports/phase-09-eval.md)): `kr/deepseek-3.2` 77% / 84%, `kr/claude-haiku-4.5` 75% / 74% (strict); 0 sai số tiền, 0 request ghi, vượt quyền 5/5 ở cả 4 lần
- [x] sửa sau eval đợt 1 (`8bb4a81`, [báo cáo đợt 2](./reports/phase-09-eval.md)): kỳ vọng S01; số tiền không đơn vị /
  model tự gắn đơn vị / bịa số → tool hỏi lại kèm lựa chọn (code, không chỉ prompt); hạng mục tự thêm nạp vào
  instructions; Ví dụ 5 bỏ "hôm qua"; ví dụ lịch lặp nhiều thứ, câu nối 2 `propose_*` trong một `run_code`, id thành viên
  giữ chỗ; nhắc `ask_user` khi hỏi bằng chữ. Bộ chấm giữ strict (mơ hồ phải `clarification`, P04 tách 2 lịch vẫn sai — lý
  do trong báo cáo)
- [x] ~~đạt ≥ 85% strict~~ — **người dùng chấp nhận hiện trạng (2026-10-11)**: 84% strict, 86–91% sau khi trừ lỗi bộ chấm, 0 sai số tiền, 0 ghi; đo lại code cuối khi router có hạn mức. Trước đây: **chưa chứng minh được**: đo đủ 57 câu sau sửa chỉ có haiku 84%
  (code chưa cuối) và deepseek 72% (code chưa cuối, hồi quy "đi chợ → food" đã sửa sau đó); code cuối mới đo 15 câu khó
  với deepseek (12/15, mơ hồ 7/9). Router trả 402 `MONTHLY_REQUEST_COUNT` cho cả hai model → chạy lại lệnh trong báo cáo
  khi có hạn mức (kèm `phase8_smoke.py`). An toàn vẫn đạt ở mọi lần: 0 sai số tiền, 0 ghi, vượt quyền 5/5
- [x] phát hành — đã phát hành trong **v1.2.0** (gộp M1–M3, fork rexviet, 2026-10-11)

## Kết quả (2026-10-10)
- Node: `npm run lint` + `npm test` (411 test) + `npm run build` xanh. Mới: `agentApply.finance.test.ts` (17 ca: merge giữ ảnh hoá đơn + mọi trường, 409 fingerprint lệch, 422 số tiền lẻ/hạng mục không còn/ngày sai/nội dung rỗng, 403 Con/Khách, xoá file sau ghi, ghi lỗi không xoá file), `db.batch.test.ts` (SQLite thật: Duyệt sửa số tiền giữ hoá đơn; nhật ký thu chi được lưu), preview + permissions.
- Agent: `uv run pytest` 513 xanh (mới: `test_money.py`, `test_finance_tools.py`, `test_eval_harness.py`), ruff + mypy strict sạch.

## Quyết định (--auto)
- **Eval nằm ở `agent/eval/`** (cùng chỗ `phase4_smoke.py`/`phase8_smoke.py`), không phải `agent/tests/eval/` như plan: `testpaths = ["tests"]` sẽ gom nó vào pytest. Bộ câu dạng **JSON** (`cases.json`) — không thêm phụ thuộc `pyyaml`. LLM-judge tuỳ chọn không làm (YAGNI).
- Số tiền: số trần < 1.000 ("đi chợ hết 150"), đuôi 2 chữ số sau đơn vị ("1tr50": 1,5 triệu hay 1.050.000?), "1,5"/"1.500k" không rõ, hai số cách nhau bằng khoảng trắng → **từ chối, model hỏi lại**. Đuôi 1 chữ số = phần mười ("1tr2"), 3 chữ số = theo vị trí ("1tr250", "1tr050").
- Khoản CHI: hạng mục phải là mặc định chưa ẩn hoặc gia đình tự thêm (Python + Node cùng luật); không rõ → hỏi lại kèm ≤ 10 lựa chọn (tự thêm trước, "Khoản khác" cuối). Khoản THU: chữ tự do như form (gợi ý `INCOME_CATEGORIES`). Không đổi được thu ↔ chi qua trợ lý.
- Nội dung bỏ trống khi tạo → lấy tên hạng mục; Node từ chối nội dung rỗng (form app bắt buộc). Ví bỏ trống → mặc định của app (Ngân hàng), thẻ Duyệt ghi ví khi có.
- Sửa/xoá theo id hoặc nội dung; khớp nhiều → ưu tiên giao dịch 31 ngày gần đây, còn nhiều → hỏi lại (nhãn "Nội dung — 250.000₫ — dd/MM").
- Admin/Thành viên sửa/xoá được mọi giao dịch (đúng như `POST/DELETE /api/finance`, không chặn theo người tạo).
- `BUILTIN_EXPENSE_CATEGORIES` tách sang `src/utils/builtinExpenseCategories.ts` (không import i18n) để server dùng chung.
- **Assistant cũ: KHÔNG gỡ** — chưa đủ điều kiện (eval chưa chạy thật, chưa bản nào phát hành); khuyến nghị + lộ trình ở [báo cáo](./reports/phase-09-eval.md).
- Sửa lỗi có sẵn: `saveTransaction` tạo/sửa ghi nhật ký rồi `writeRaw(db)` đè mất dòng nhật ký; form sửa giao dịch xoá ảnh hoá đơn cũ **trước** khi ghi (ghi lỗi → bản ghi trỏ tới file đã mất) → nay xoá sau khi ghi.

## Code review (7.5/10, không Critical) — đã xử lý
- H1 số trần "150" thành 150 đ → từ chối < 1.000. H2 "1 triệu 50" thành 1,5 triệu → từ chối đuôi 2 chữ số. H3 "10 20" dính thành 1.020 → từ chối số cách khoảng trắng (trừ "1 000 000"). M1 đuôi quá dài ("1tr2000000") → từ chối.
- M2 eval: đoán hạng mục ở câu mơ hồ bị tính "sai số tiền" → tách cột "Thu chi ngoài ý". M3 eval: "1,5" bị đọc thành 15 → chỉ bỏ dấu khi đúng nhóm nghìn. Thêm câu A09 "đi chợ hết 150".
- M4 (có sẵn) xoá ảnh hoá đơn trước khi ghi → sau khi ghi. L1 xoá từng file riêng. L2 Node từ chối nội dung rỗng.
- Để nguyên: L3 nhãn hạng mục ở nhật ký hoạt động dùng bảng riêng (có sẵn, chỉ là chữ); L4 số tiền trong nhật ký nay dạng vi-VN "250.000".

## Success Criteria
Test xanh; eval ≥ 85% với model khuyến nghị; 0 operation thu chi sai số tiền trong eval.

## Risk Assessment
Sai số tiền/hạng mục → parse trong code + preview số đầy đủ + bắt buộc Duyệt.

## Security Considerations
Con/khách không đề xuất được thu chi (tool đọc 403 → hỏi lại không có ý nghĩa; tool đề xuất kiểm role sớm, apply kiểm lại).

## Next Steps
Kết thúc plan; mục v2 trong spec (đọc tài sản/nợ/tiết kiệm/giấy tờ/sức khoẻ) là plan mới.
