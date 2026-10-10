# Phase 6 — UI trợ lý + Thiết lập

**Priority:** P1 · **Effort:** 8h · **Status:** Pending

## Context Links
- [DESIGN.md](../../DESIGN.md) — **đọc trước**, bám checklist cuối file
- `src/components/Assistant.tsx` (325 dòng; luồng `runAction` hiện tại), `src/components/Settings.tsx` (khối AI/Gemini key), `src/i18n/locales/{vi,en,zh}.json` (khối `assistant`)

## Overview
Giữ khung trợ lý hiện tại, thay luồng gửi tin và hành động: hội thoại nhiều lượt, card Duyệt do server dựng, nút chọn nhanh khi agent hỏi lại. Thêm khối trạng thái agent ở Thiết lập.

## Requirements
- Gửi tin → `POST /api/assistant/agent`; 503 `fallback` → gọi `/api/assistant/chat` như cũ (giữ code cũ). 429 → "Trợ lý đang bận, thử lại sau ít giây".
- Mở trợ lý → tải `conversations/latest`; nút "Cuộc trò chuyện mới".
- `kind=proposal` → card: danh sách dòng preview (tone `delete` màu đỏ, `edit` hiện `cũ → mới`), nút **Duyệt** / **Huỷ**; đang gửi → khoá nút (chống bấm 2 lần); kết quả từng dòng sau apply; 409 guard → thông báo "dữ liệu vừa thay đổi, hỏi lại trợ lý".
- `kind=clarification` → câu hỏi + nút `options` (bấm = gửi tin nhắn đó).
- Proposal hết hạn → card mờ + nhãn "Đã hết hạn". Proposal `failed` (app khởi động lại giữa lúc ghi) → "Không chắc đã ghi xong — kiểm tra lại".
- Thiết lập → AI (admin): công tắc "Trợ lý nâng cao", trạng thái `reachable / llmConfigured / model / version`, ghi chú "dữ liệu được gửi tới nhà cung cấp LLM đã cấu hình".
- i18n đủ `vi`, `en`, `zh` cho chuỗi mới.
- Giữ nhập giọng nói hiện có.

## Related Code Files
- Sửa: `src/components/Assistant.tsx`, `src/components/Settings.tsx`, `src/i18n/locales/{vi,en,zh}.json`
- Tạo (nếu Assistant.tsx vượt ~450 dòng): `src/components/assistant/ProposalCard.tsx`, `ClarificationChips.tsx`

## Implementation Steps
1. Đọc DESIGN.md; tái dùng lớp Tailwind sẵn có (card, nút chính/phụ, màu nguy hiểm).
2. Tách `ProposalCard` + `ClarificationChips` (props thuần, không gọi API).
3. Đổi luồng gửi tin + fallback; tải hội thoại gần nhất.
4. Khối Thiết lập.
5. Chạy thử Sáng/Tối, màn hình hẹp (safe-area), giọng nói.

## Todo
- [ ] ProposalCard / ClarificationChips
- [ ] Luồng agent + fallback
- [ ] Hội thoại gần nhất / mới
- [ ] Thiết lập agent
- [ ] i18n 3 ngôn ngữ
- [ ] Soát DESIGN.md checklist

## Success Criteria
`npm run lint` xanh; chạy tay đủ 3 kind ở cả 2 theme + mobile; tắt agent → trợ lý cũ vẫn chạy.

## Security Considerations
Không hiển thị gì về key/base_url; card chỉ render dữ liệu server dựng (không render HTML từ model).

## Next Steps
Phase 7.
