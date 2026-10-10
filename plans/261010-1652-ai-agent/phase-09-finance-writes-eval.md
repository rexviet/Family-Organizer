# Phase 9 — Ghi Thu chi + eval đầy đủ (M3)

**Priority:** P2 · **Effort:** 6h · **Status:** Pending

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
- [ ] parse tiền
- [ ] 3 tool thu chi
- [ ] apply + preview thu chi
- [ ] eval 50 câu + báo cáo
- [ ] phát hành 1.4.0

## Success Criteria
Test xanh; eval ≥ 85% với model khuyến nghị; 0 operation thu chi sai số tiền trong eval.

## Risk Assessment
Sai số tiền/hạng mục → parse trong code + preview số đầy đủ + bắt buộc Duyệt.

## Security Considerations
Con/khách không đề xuất được thu chi (tool đọc 403 → hỏi lại không có ý nghĩa; tool đề xuất kiểm role sớm, apply kiểm lại).

## Next Steps
Kết thúc plan; mục v2 trong spec (đọc tài sản/nợ/tiết kiệm/giấy tờ/sức khoẻ) là plan mới.
