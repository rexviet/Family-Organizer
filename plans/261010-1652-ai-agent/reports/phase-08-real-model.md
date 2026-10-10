# Phase 8 — thử 10 câu Việc/Lịch với model thật (2026-10-10)

> **Kết quả hiện hành:** `kr/deepseek-3.2` **7/10 và 8/10**, 0 request ghi → đạt (xem "Lần đo 2"). Lần đo 1 qua OpenRouter không đo được — giữ lại bên dưới.

- Runner: `agent/eval/phase8_smoke.py` (dùng lại khung `phase4_smoke.py`; không nằm trong image, không chạy bởi pytest). Chạy `run_turn` THẬT
  (instructions, 9 tool đọc, 3 tool đi chợ, 6 tool Việc/Lịch, `ask_user`, CodeMode, EndWhenSettled, output validator); app Node giả bằng
  `httpx.MockTransport`. Người hỏi: Mẹ Lan (`member`), hôm nay Thứ Bảy 2026-10-10. Mỗi câu một lượt riêng, không history.
- Bộ chấm đòi đúng MỘT operation với đúng id/ngày (vd. câu 1: `task.create` giao `m4`, hạn `2026-10-11 18:00`); câu 10 mơ hồ chấm
  `clarification` hoặc `answer` có "?".
- Runner có lùi + thử lại khi nhà cung cấp trả 429 (15 → 30 → 60 s, tối đa 3 lần ≈ 105 s/câu rồi ghi lỗi nhà cung cấp), nghỉ giữa các câu.
- Gọi qua OpenRouter (`https://openrouter.ai/api/v1`); khoá API chỉ nạp từ `agent/.env`, không ghi ở đâu.

## Lần đo 2 — `kr/deepseek-3.2` qua router local (2026-10-10) — **ĐẠT**

Router local `http://localhost:20128/v1` đã bật (`/v1/models` có `kr/deepseek-3.2`, `kr/claude-haiku-4.5`). Env truyền inline
(`AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x AGENT_LLM_MODEL=kr/deepseek-3.2`), không nạp `agent/.env`.
Lệnh: `uv run python eval/phase8_smoke.py --pause 2 --report <tmp>`, 2 lượt liên tiếp.

| Lượt | Điểm | Request tới app | Method ≠ GET | 429 còn lại | Chậm nhất |
| :-- | --: | --: | --: | --: | --: |
| 1 | **7/10** | 16 | **0** | 0 | 23 s |
| 2 | **8/10** | 15 | **0** | 0 | 40 s |

Tiêu chí phase 8 (≥ 7/10, 0 request ghi) **đạt cả 2 lượt**. Không có lỗi nhà cung cấp, không câu nào treo.

Đọc tay các câu FAIL:

| Lượt | # | Model làm gì | Phân loại |
| :-- | :-- | :-- | :-- |
| 1 | 3 | Hỏi lại "việc hiện có hạn ngày nào?" bằng chữ, **không đọc** danh sách việc (0 tool call) | lỗi thật (nhẹ — không sai dữ liệu) |
| 1 | 9 | `ask_user` hỏi "mỗi buổi học piano kéo dài bao lâu?" (có 3 lựa chọn) thay vì tự đặt 1 tiếng | bộ chấm khắt khe — hỏi lại hợp lý |
| 1 | 10 | Câu mơ hồ (2 lịch sinh nhật) nhưng **đề xuất xoá luôn `p3` "Sinh nhật bà"** không hỏi lại | lỗi thật — vẫn chỉ là đề xuất, phải Duyệt mới xoá |
| 2 | 7 | Hỏi "tên sự kiện họp lớp là gì?" thay vì tìm (0 tool call) | lỗi thật (nhẹ) |
| 2 | 9 | Tách thành **2 lịch** weekly `[2]` (13/10) + `[4]` (15/10), cùng 17:00 — tương đương về nghĩa với một lịch `[2, 4]` | bộ chấm khắt khe (kết quả dùng được, chỉ kém gọn) |

Nếu tính các câu "bộ chấm khắt khe" là đạt: lượt 1 **8/10**, lượt 2 **9/10**. Các câu đúng đều đúng id/ngày/giờ (giao `m4`,
hạn `2026-10-11 18:00`, dời `p1` kèm giờ kết thúc tự dời, `t7` sang 12/10…). Lượt 2 câu 10 hỏi lại đúng thiết kế
(`ask_user` với 2 lựa chọn "Sinh nhật bà"/"Sinh nhật Bin").

Gợi ý (không sửa code lần này — không phải lỗi): thêm ví dụ lịch lặp nhiều thứ trong tuần (`recurrence_weekdays=[2, 4]`)
vào instructions để model không tách lịch; câu mơ hồ kiểu "xoá lịch X" khi có > 1 khớp có thể cho tool xoá tự từ chối và
yêu cầu hỏi lại (giống `records.resolve` khi tên trùng) — cân nhắc cùng đợt chỉnh prompt sau phase 9.

## Kết luận lần đo 1 (OpenRouter)

**Chưa đo được chất lượng phase 8 với model thật** — cả hai model thử đều không dùng được:

| Model | Kết quả | Nguyên nhân | Lỗi từ |
| :-- | :-- | :-- | :-- |
| `google/gemma-4-26b-a4b-it:free` | **không đo được** — 429 upstream liên tục (9/10 câu ở lượt 1) | giới hạn tần suất của gói miễn phí; lượt chạy lại kẹt ~40 phút trong backoff nên dừng, không chạy lại | nhà cung cấp |
| `mistralai/mistral-nemo` | **0/10, 0/10** (2 lượt) | model **không gọi tool**: 0 tool call ở cả 20 lượt — viết code/hàm `propose_*` ra chữ trong câu trả lời thay vì gọi `run_code` | model |

- **Đối chứng:** chạy bộ 10 câu phase 4 (đi chợ — model khác từng đạt 9–10/10) với `mistral-nemo`: **3/10**, cũng **0 tool call**;
  3 câu "PASS" là trả lời bịa không đọc dữ liệu. ⇒ lỗi do khả năng gọi tool của model, **không phải** do code phase 8.
- **An toàn:** 0 request ghi tới app ở mọi lượt (Gemma 10 request, mistral-nemo 20 + 10 request — toàn `GET /api/users` đầu lượt).
  Câu trả lời "đã dời…" ở câu 7 (lượt 2) không đi kèm đề xuất nào → không có gì bị ghi; output validator bắt được ở các câu 5, 6, 9
  (model nhận "chưa gọi propose_*") nhưng model vẫn không gọi tool.
- Không có 400 lạ từ nhà cung cấp. Câu 2 lượt 2: model hết retry → trả lời thân thiện `MSG_GAVE_UP` (đúng thiết kế, không 502).
- **Không sửa code production**: không thấy lỗi thật. Một quan sát về prompt: ở câu 1, mistral-nemo chép nguyên ví dụ giao việc trong
  instructions (`assignee_id="u_bin"`) dù bảng thành viên có id khác (`m4`). Nếu model gọi tool thật, `propose_create_task` sẽ từ chối
  id lạ (ToolError) nên không sai dữ liệu; có thể cân nhắc đổi ví dụ sang id dạng `<id của Bin trong bảng thành viên>` khi làm eval M3.
- **Việc còn lại:** chạy lại `phase8_smoke.py` với model có tool calling tốt (lần trước đạt 9–10/10 ở phase 4: `kr/deepseek-3.2`,
  `kr/claude-haiku-4.5` qua router local `localhost:20128`, hôm nay router không chạy) trước khi phát hành 1.3.0.

## Gemma — lượt 1 (dừng, không chạy lại)

1/10 câu tới được model (câu 2: có đề xuất nhưng chấm FAIL — runner lượt đó chưa in operation nên không rõ sai ở đâu); 9/10 câu
`ModelHTTPError 429 "Provider returned error"` từ OpenRouter. Lượt 2 (có backoff) kẹt ~40 phút ở 429 → phiên chính dừng.

## mistral-nemo — lượt 1

| # | Câu hỏi | Kết quả | Kind | Model req | Tool call | GET app | Giây | Thử lại 429 | Ghi chú |
| :-- | :-- | :-- | :-- | --: | --: | --: | --: | --: | :-- |
| 1 | Giao bé Bin cho mèo ăn lúc 6 giờ tối mai | FAIL | answer | 1 | 0 | 1 | 2.5 | 0 | ```python import asyncio  await asyncio.gather(     propose_create_task(title='Cho mèo ăn', assignee_id='u_bin', due_date='2026-10-11 18:00' |
| 2 | Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau | FAIL | answer | 2 | 0 | 1 | 3.6 | 0 | ổn |
| 3 | Dời việc sửa vòi nước sang thứ Hai tuần sau | FAIL | answer | 1 | 0 | 1 | 46.1 | 0 | Dịch vụ: Family Organizer Người dùng: Mẹ Lan Ngày: 2026-10-10 (Thứ Bảy)  Dịch vụ Family Organizer cung cấp các tính năng sau:  1. Danh sách  |
| 4 | Chuyển việc dọn phòng cho bé Bin | FAIL | answer | 1 | 0 | 1 | 8.0 | 0 | Dưới đây là danh sách các việc còn lại chưa được xong:  / Tên / Trạng thái / Được giao cho / Hạn deadline / /---/---/---/---/ / Rửa phòng /  |
| 5 | Xoá việc họp phụ huynh | FAIL | answer | 1 | 0 | 1 | 3.0 | 0 | Xoá việc họp phụ huynh:  async def propose_delete_plan(*, plan: str) -> str:     ...  await propose_delete_plan(plan="Họp phụ huynh") |
| 6 | Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau | FAIL | answer | 2 | 0 | 1 | 15.0 | 0 | Bạn có phải thêm lịch khám răng cho bé Na vào ngày 2026-10-16 (Thứ Sáu) không? |
| 7 | Dời buổi họp lớp sang 3 giờ chiều mai | FAIL | answer | 1 | 0 | 1 | 4.2 | 0 | Dịch vụ này được thiết kế để giúp gia đình quản lý các hoạt động hàng ngày của họ, bao gồm lịch trình, nhiệm vụ, và chi tiêu. Bạn có thể sử  |
| 8 | Huỷ lịch đi bơi chủ nhật này | FAIL | answer | 1 | 0 | 1 | 1.9 | 0 | ```python import asyncio  await asyncio.gather(     propose_delete_plan(plan="Đi bơi Chủ nhật 14/10"), ) ``` |
| 9 | Thêm lịch học piano mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau | FAIL | answer | 1 | 0 | 1 | 2.8 | 0 | Câu hỏi gì về dữ liệu gia đình của bạn? |
| 10 | Xoá lịch sinh nhật | FAIL | answer | 1 | 0 | 1 | 5.1 | 0 | Bạn có thể xoá lịch sinh nhật bằng cách gọi hàm `propose_delete_plan` với id của lịch sinh nhật đó. Bạn có thể lấy id của lịch sinh nhật từ  |

## mistral-nemo — lượt 2

| # | Câu hỏi | Kết quả | Kind | Model req | Tool call | GET app | Giây | Thử lại 429 | Ghi chú |
| :-- | :-- | :-- | :-- | --: | --: | --: | --: | --: | :-- |
| 1 | Giao bé Bin cho mèo ăn lúc 6 giờ tối mai | FAIL | answer | 1 | 0 | 1 | 3.9 | 0 | ```python import asyncio  await asyncio.gather(     propose_create_task(title='Cho mèo ăn', assignee_id='u_bin', due_date='2026-10-11 18:00' |
| 2 | Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau | FAIL | answer | 3 | 0 | 1 | 13.7 | 0 | Mình chưa xử lý được yêu cầu này. Bạn thử diễn đạt lại hoặc hỏi ngắn gọn hơn giúp mình nhé. |
| 3 | Dời việc sửa vòi nước sang thứ Hai tuần sau | FAIL | answer | 1 | 0 | 1 | 6.7 | 0 | Dưới đây là các công việc có nhiều việc chưa xong nhất:  / Tên / Số lượng việc chưa hoàn thành / /---/---/ / Bố Minh / 5 / / Mẹ Lan / 4 / /  |
| 4 | Chuyển việc dọn phòng cho bé Bin | FAIL | answer | 1 | 0 | 1 | 6.1 | 0 | Dưới đây là danh sách các việc cần hoàn thành:  / Tên / Trạng thái / Người giao / Hạn / /---/---/---/---/ / Dọn phòng / Đang làm / Mẹ Lan /  |
| 5 | Xoá việc họp phụ huynh | FAIL | answer | 2 | 0 | 1 | 3.8 | 0 | I apologize for the confusion. You are correct that I did not call any propose_* tool. There was no change to the data. |
| 6 | Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau | FAIL | answer | 2 | 0 | 1 | 7.0 | 0 | I'm sorry, I misunderstood your previous instruction. You're right, I should have called a propose_* function to suggest the change. I'll fi |
| 7 | Dời buổi họp lớp sang 3 giờ chiều mai | FAIL | answer | 1 | 0 | 1 | 3.1 | 0 | Dịch họp buổi học của bé Na (id m3) vào ngày mai (2026-10-11) đã được dời tại 3 giờ chiều. |
| 8 | Huỷ lịch đi bơi chủ nhật này | FAIL | answer | 1 | 0 | 1 | 1.3 | 0 | ```python import asyncio  await asyncio.gather(     propose_delete_plan(plan="Đi bơi Chủ Nhật 14h"), ) ``` |
| 9 | Thêm lịch học piano mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau | FAIL | answer | 2 | 0 | 1 | 6.3 | 0 | I'm sorry for the confusion earlier. You're right, I should have called the appropriate `propose_*` function after making changes. Here's th |
| 10 | Xoá lịch sinh nhật | FAIL | answer | 1 | 0 | 1 | 7.0 | 0 | Bạn có thể xóa lịch sinh nhật bằng cách gọi hàm `propose_delete_plan` với id của lịch sinh nhật đó. Bạn có thể tìm id của lịch sinh nhật đó  |

## Đối chứng mistral-nemo — bộ 10 câu phase 4

```
 1 FAIL read      -> answer        req=1 tools=0 gets=1   8.4s  Hôm nay bé Na có những việc gì? | ```python import asyncio  tasks, members = await asyncio.gather(list_tas
 2 PASS read      -> answer        req=1 tools=0 gets=1   2.1s  Ai đang có nhiều việc chưa xong nhất? | 1. Mẹ Lan: 1 2. Bé Na: 0 3. Bé Bin: 0
 3 FAIL read      -> answer        req=1 tools=0 gets=1   3.7s  Trong danh sách đi chợ còn thiếu gì? | Dưới là danh sách các món đang có trong danh sách đi chợ:  | Tên mó
 4 PASS read      -> answer        req=1 tools=0 gets=1   1.8s  Nhà mình có mấy thành viên và ai là trẻ  | Có, nhà mình có hai thành viên là trẻ em. Bé Na (id m3) và Bé B
 5 PASS read      -> answer        req=1 tools=0 gets=1   3.7s  Việc nào của mẹ Lan hạn trong tuần này? | Mẹ Lan có hai việc hạn trong tuần này:  - Việc 1: Đi chợ, đến hạ
 6 FAIL propose   -> answer        req=2 tools=0 gets=1   6.9s  Thêm sữa chua và 2 chục trứng vào danh s | Có phải là một lỗi trong code của bạn. Vui lòng kiểm tra lại và
 7 FAIL propose   -> answer        req=2 tools=0 gets=1   6.3s  Mai đi chợ nhớ mua rau muống với cà chua | ```json {   "code": "import asyncio\nmembers = await list_membe
 8 FAIL propose   -> answer        req=1 tools=0 gets=1  15.8s  Danh sách đã có sữa tươi rồi, thêm bột g | Dạ, Mẹ Lan. Hôm nay là ngày 10 tháng 10 năm 2026.  Ai có nhiều 
 9 FAIL ambiguous -> answer        req=1 tools=0 gets=1  31.5s  Thêm cái đó vào danh sách nhé | Bạn có thể sử dụng các tool sau đây để tương tác với ứng dụng:  | Tên | Mô
10 FAIL ambiguous -> answer        req=1 tools=0 gets=1  24.9s  Giao việc cho bé | Dưới đây là danh sách các việc có thể giao cho bé Na (id m3) trong tuần này:  | Tiêu đề
TOTAL 3/10  model=mistralai/mistral-nemo  app_requests=10 writes=0
```
