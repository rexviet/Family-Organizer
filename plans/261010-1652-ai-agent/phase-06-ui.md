# Phase 6 — UI trợ lý + Thiết lập

**Priority:** P1 · **Effort:** 8h · **Status:** Done (2026-10-10)

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
- [x] ProposalCard / ClarificationChips (`src/components/assistant/`)
- [x] Luồng agent + fallback (503 `fallback` → `/api/assistant/chat` cũ, giữ nguyên code cũ)
- [x] Hội thoại gần nhất / mới
- [x] Thiết lập agent (`src/components/assistant/AgentSettings.tsx`, gắn ở tab Hệ thống & Sao lưu)
- [x] i18n 3 ngôn ngữ (`assistant.agent.*`)
- [x] Soát DESIGN.md checklist

## Kết quả (2026-10-10)

- `npm run lint && npm test && npm run build` xanh (346 test; mới: `src/utils/assistantAgent.test.ts` 18 test, `publicProposal.uncertain` trong `server/agentRoutes.test.ts`).
- Chạy tay (bản build, thư mục tạm, agent giả trả đủ 3 kind) trên Chrome: tắt agent → trợ lý cũ trả lời; bật ở Thiết lập (hiện
  Kết nối/Mô hình AI/Tương thích/Model/Phiên bản); hỏi lại → chip → bấm chip gửi tin; đề xuất thêm → bấm Duyệt 2 lần liền → đúng 2 món
  (kết quả từng dòng "Đã ghi"); đề xuất sửa+xoá (dòng xoá màu đỏ) → sửa món từ ngoài → Duyệt → "Dữ liệu vừa thay đổi…"; Huỷ;
  hết hạn (mờ + "Đã hết hạn"); `failed` sau khởi động lại → "Không chắc đã ghi xong — kiểm tra lại"; 429 → báo bận; tải lại trang → hội thoại
  còn nguyên; "Cuộc trò chuyện mới"; agent lỗi giữa chừng → rơi về trợ lý cũ. Sáng + Tối; khung 390 px (nút "mới" chỉ còn icon). Không lỗi console.
- Chưa thử: nhập giọng nói trên thiết bị thật (code giọng nói giữ nguyên, dùng chung `sendQuestion`); iPhone thật (safe-area mới thêm cho lớp phủ).

### Quyết định khi làm (--auto)
- Server thêm `uncertain` vào `publicProposal` (failed do khởi động lại giữa lúc ghi, so khớp `STALE_APPLY_ERROR`) — UI không đoán từ chuỗi lỗi.
- 429: hiện thông điệp server nếu có (hết 20 lượt/giờ khác "bận vài giây"), không có mới dùng "Trợ lý đang bận…".
- Agent lỗi khi chạy → chuyển cả phiên sang trợ lý cũ (đến lần mở trợ lý sau sẽ hỏi lại `conversations/latest`).
- Mỗi lần mở trợ lý tải lại hội thoại gần nhất từ server (nguồn chân lý); proposal pending quá hạn hiển thị "Đã hết hạn" ngay ở client
  (đồng hồ 30 s) dù server chưa dọn.
- Khối Thiết lập tách component riêng (Settings.tsx đã 2000+ dòng); công tắc dùng lại mẫu nút "ĐANG BẬT/ĐANG TẮT" của Telegram backup.
- Logic thuần tách `src/utils/assistantAgent.ts` để TDD (repo không có thư viện test React); component chỉ nhận props, không gọi API.

### Code review (7.5/10, 0 Critical) — đã sửa
- H1 tải lịch sử về muộn ghi đè tin vừa gửi → `busyRef` (lượt gửi/đặt lại đang chạy thì không ghi đè) + khoá gửi khi đang tải lịch sử.
- H2 `conversationId` đã bị dọn → kẹt 404 mãi → 404/409 thành `reset` (bỏ id, lượt sau tạo hội thoại mới; đã chạy thử).
- H3 "Cuộc trò chuyện mới" chạy song song với gửi tin → dùng chung cờ bận.
- M1 body 2xx sai dạng → lỗi thường, không ném TypeError. M3 bỏ `slate-700` (không remap theme). M4 giọng nói gọi `sendQuestion` mới nhất qua ref.
- L1 chống bấm Duyệt 2 lần bằng ref (bấm đồng bộ 2 lần → đúng 1 lần ghi). L4 cuộn trong khung chat thay vì `scrollIntoView`.
- Để lại: M2 (503 không có `fallback` từ proxy → báo lỗi, không tự rơi về trợ lý cũ — giữ đúng hợp đồng server), L2 (card `applying` không tự
  làm mới — hiếm, mở lại trợ lý là thấy trạng thái mới), L3 (lệch đồng hồ client — server vẫn chặn), L5.

## Success Criteria
`npm run lint` xanh; chạy tay đủ 3 kind ở cả 2 theme + mobile; tắt agent → trợ lý cũ vẫn chạy.

## Security Considerations
Không hiển thị gì về key/base_url; card chỉ render dữ liệu server dựng (không render HTML từ model).

## Next Steps
Phase 7.
