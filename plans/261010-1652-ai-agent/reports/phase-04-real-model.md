# Phase 4 — thử 10 câu với model thật (2026-10-10)

- Runner: `agent/eval/phase4_smoke.py` (không nằm trong image, không chạy bởi pytest). Chạy `run_turn` THẬT (instructions, 9 tool đọc, 3 tool đi chợ,
  `ask_user`, CodeMode, EndWhenSettled, output validator) qua router `http://localhost:20128/v1`; app Node được giả bằng `httpx.MockTransport`
  với dữ liệu của spike phase 1 theo đúng dạng JSON của API thật (có `comments/history/proofImage` để chứng minh tool cắt trường).
- Người hỏi: Mẹ Lan (`member`), hôm nay Thứ Bảy 2026-10-10. Mỗi câu là một lượt riêng, không history.
- **Điều chỉnh so với spike:** câu 5 ("hạn trong tuần này"): spike đặt "Đóng tiền điện" hạn 10-12; nay "tuần này = Thứ Hai–Chủ nhật" = 10-05…10-11 nên dữ liệu
  đặt hạn vào Chủ nhật 10-11, và bộ chấm đòi thêm "không nhắc Họp phụ huynh (10-14)" → phải lọc đúng tuần.
- Bộ chấm: từ khoá như spike, nhưng đề xuất chấm trên `operations` thật (kind `proposal`), câu mơ hồ chấm kind `clarification` hoặc `answer` có dấu "?".
- Cột "GET app" gồm cả 1 request lấy thành viên đầu lượt; mỗi endpoint chỉ gọi tối đa 1 lần/lượt (cache hoạt động).

## Kết quả chính — `kr/deepseek-3.2` (lần 1)

| # | Câu hỏi | Loại | Kết quả | Kind | Model req | Tool call | GET app | Giây | Ghi chú |
| :-- | :-- | :-- | :-- | :-- | --: | --: | --: | --: | :-- |
| 1 | Hôm nay bé Na có những việc gì? | read | PASS | answer | 2 | 3 | 2 | 12.1 | Hôm nay bé Na có 2 việc:  - **Đánh răng** (hạn 7:00, chưa làm)   - **Làm bài tập toán** (hạn 19:00, chưa làm)  |
| 2 | Ai đang có nhiều việc chưa xong nhất? | read | PASS | answer | 2 | 3 | 2 | 29.0 | Dựa trên phân tích, ai đang có nhiều việc chưa xong nhất:  - **Bé Na**: 3 việc - Mẹ Lan: 2 việc   - Bố Minh: 1 |
| 3 | Trong danh sách đi chợ còn thiếu gì? | read | PASS | answer | 2 | 3 | 3 | 19.0 | Danh sách đi chợ hiện tại có 2 món: - Sữa tươi: 2 hộp - Dầu ăn: 1 chai  Chưa có thực đơn tuần nào đang dùng. V |
| 4 | Nhà mình có mấy thành viên và ai là trẻ em? | read | PASS | answer | 2 | 2 | 1 | 12.3 | Gia đình có **4 thành viên**:  - **Người lớn:** Bố Minh (admin), Mẹ Lan (member) - **Trẻ em:** Bé Na, Bé Bin ( |
| 5 | Việc nào của mẹ Lan hạn trong tuần này? | read | PASS | answer | 2 | 2 | 2 | 12.7 | Mẹ Lan có **1 việc** hạn trong tuần này:  • **Đóng tiền điện** – hạn đến ngày mai (11/10) lúc 12:00, trạng thá |
| 6 | Thêm sữa chua và 2 chục trứng vào danh sách đi chợ | propose | PASS | proposal | 1 | 2 | 2 | 2.9 | ops='Sữa chua Trứng' |
| 7 | Mai đi chợ nhớ mua rau muống với cà chua giúp mình | propose | PASS | proposal | 1 | 2 | 2 | 17.1 | ops='Rau muống Cà chua' |
| 8 | Danh sách đã có sữa tươi rồi, thêm bột giặt và nước rửa chén nhé | propose | PASS | proposal | 1 | 2 | 2 | 3.8 | ops='Bột giặt Nước rửa chén' |
| 9 | Thêm cái đó vào danh sách nhé | ambiguous | PASS | clarification | 2 | 2 | 1 | 12.3 | Bạn muốn thêm món gì vào danh sách đi chợ? |
| 10 | Giao việc cho bé | ambiguous | PASS | answer | 1 | 0 | 1 | 3.9 | Bạn muốn giao việc gì cho bé nào? Gia đình có 2 bé: Bé Na và Bé Bin.   Bạn có thể giao: - Việc cụ thể gì (tiêu |

**Model `kr/deepseek-3.2`: 10/10** — request tới app: 18, trong đó method ≠ GET: 0.

## Các lần chạy

| Lần | Model | Điểm | Request tới app | Ghi (≠ GET) | Ghi chú |
| :-- | :-- | :-- | --: | --: | :-- |
| 1 | `kr/deepseek-3.2` | **10/10** | 18 | **0** | bảng trên; chậm nhất 29 s (câu tổng hợp "ai nhiều việc nhất", 2 request model) |
| 2 | `kr/deepseek-3.2` | **10/10** | 18 | **0** | câu 9 trả lời bằng chữ có dấu "?" (không gọi `ask_user`), câu 10 gọi `ask_user` — cả hai đều chấp nhận được |
| 3 | `kr/claude-haiku-4.5` | **10/10** | 18 | **0** | nhanh: 1.4–7 s mỗi câu; cả 2 câu mơ hồ trả lời bằng chữ + "?" |
| 4 | `kr/deepseek-3.2` | **10/10** | 18 | **0** | sau khi sửa review (CodeGuard, validator ngôi thứ nhất, rollback…). Câu 3 một lần dùng 6 request/78 s (chạm giới hạn mà vẫn trả lời được); chạy lại riêng 2 lần: 2 request, 13–17 s — nhiễu của router, không tái hiện |
| 5 | `kr/deepseek-3.2` | **9/10** | 18 | **0** | sau vòng sửa re-review cuối (cờ `tool_failed`, NFC, lỗi provider → 502). Câu 10 "Giao việc cho bé" FAIL theo bộ chấm: model hỏi lại bằng chữ nhưng không có dấu "?" (vẫn không đề xuất bừa) — lỗi chấm heuristic hơn là lỗi hành vi |

## Nhận xét
- Đạt ngưỡng ≥ 7/10 (5 lần: 10, 10, 10, 10, 9), **không lượt nào ghi dữ liệu** (mọi request tới app đều `GET`; hook của client cũng chặn mọi method khác/đường dẫn ngoài allowlist).
- 3 câu đề xuất đều kết thúc sau **1 request model** (EndWhenSettled), proposal đúng; câu "đã có sữa tươi rồi, thêm bột giặt…" model đề xuất đúng 2 món.
- Câu tổng hợp ("ai nhiều việc chưa xong nhất") giờ xong bằng 2 request (1 `run_code` gộp bằng `asyncio.gather` + câu trả lời), không còn dính `UsageLimitExceeded` như spike — hiệu quả của date-range filter + instructions khuyến khích một chương trình.
- "Tuần này" được lọc đúng Thứ Hai–Chủ nhật ở cả 3 lần (không nhắc việc ngày 10-14).
- Câu mơ hồ: model đôi khi hỏi bằng chữ thay vì gọi `ask_user` — vẫn đúng hành vi (không đề xuất bừa). Khi gọi `ask_user`, câu hỏi hiện nguyên văn do tool ghi.
- Mẫu nhỏ (10 câu, dữ liệu giả); eval 50 câu đầy đủ là việc của phase 9.
