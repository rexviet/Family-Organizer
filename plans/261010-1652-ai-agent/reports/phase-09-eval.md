# Phase 9 — Eval đầy đủ + khuyến nghị về assistant cũ (2026-10-10)

## Trạng thái: khung eval xong, **chạy với model thật hoãn**

Router LLM local (`http://localhost:20128/v1`) không bật lúc làm phase 9 (`curl …/v1/models` → không kết nối được;
chạy thử 1 câu ra `ModelAPIError: Connection error.`). Khung eval đã chạy trọn đường ống bằng FunctionModel trong
unit test, nên lần chạy thật chỉ còn là chạy lệnh dưới.

### Lệnh chạy (mỗi model ≥ 2 lần — phase 1/4 cho thấy điểm dao động giữa các lần)

```sh
cd agent
AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x \
  uv run python eval/run_eval.py --models kr/deepseek-3.2 kr/claude-haiku-4.5 --runs 2
```

Mỗi model ghi `reports/eval-<model>-<ngày>.md` (bảng tổng hợp theo lần + chi tiết từng câu). Lệnh trả mã 1 nếu có
operation thu chi sai số tiền hoặc request ghi tới app. Sau khi chạy: điền bảng "Model đã kiểm chứng" trong
`agent/README.md`.

## Khung eval

| File | Nội dung |
| :--- | :--- |
| `agent/eval/cases.json` | 57 câu: 15 đọc (gồm 6 câu số liệu thu chi), 24 ghi (Đi chợ 4, Việc 6, Lịch 4, Thu chi 10), 4 câu nối (2 module/câu), 9 mơ hồ, 5 vượt quyền (đăng nhập Bé Na — child) |
| `agent/eval/fixtures/app.json` | App giả đúng dạng JSON API Node; tháng 10: chi 2.720.000, thu 15.000.000, ăn uống 370.000; có 1 giao dịch số tiền lẻ (bản ghi cũ), hạng mục tự thêm "Thú cưng", hạng mục mặc định bị ẩn |
| `agent/eval/run_eval.py` | `run_turn` thật + `httpx.MockTransport`; con/khách đọc thu chi → 403 như `requireRole`; mọi request ghi bị đếm |
| `agent/tests/unit/test_eval_harness.py` | 16 test: bộ câu hợp lệ với dữ liệu giả, luật chấm, đọc số tiền trong câu trả lời, chạy trọn 3 câu bằng FunctionModel |

Luật chấm (chi tiết ở docstring `run_eval.py`):
- **Đọc**: kind `answer`, đủ từ khoá (không dấu), không lộ từ cấm, có đúng số liệu chính — số trong câu trả lời đọc
  bằng chính `money.parse_vnd` nên "2.720.000đ", "2,72 triệu", "370k" đều nhận ("1,5" không bị đọc thành 15). LLM-judge (tuỳ chọn trong plan) **không
  làm** — regex số + từ khoá đủ cho bộ câu này (YAGNI).
- **Ghi / câu nối**: kind `proposal`, operations khớp kỳ vọng bỏ qua thứ tự, chỉ so trường được nêu; `changes` không được
  có trường thừa (đổi thứ người dùng không nói = sai).
- **Mơ hồ**: phải ra `clarification` (nghiêm như plan); cột "Lenient" đếm thêm câu hỏi lại bằng chữ có "?" để so với
  báo cáo phase 4.
- **Vượt quyền**: không có đề xuất, không lộ số liệu thu chi.
- **Sai số tiền**: đếm riêng (tiêu chí 0). Đề xuất thu chi ở câu không chờ thu chi (vd. đoán hạng mục thay vì hỏi
  lại) đếm ở cột "Thu chi ngoài ý" — câu đó đã FAIL, nhưng không lẫn với sai số tiền.

## Khuyến nghị: **chưa gỡ** `/api/assistant/chat`

Plan đặt điều kiện gỡ: eval ≥ 85% **và** agent đã chạy ổn ≥ 1 bản phát hành. Hiện chưa đạt cả hai:
1. Eval phase 9 chưa chạy với model thật (router tắt).
2. 1.2.0/1.3.0/1.4.0 mới ở dạng nháp — chưa bản nào tới tay người dùng, RAM/độ ổn định trên Pi chưa đo (hoãn từ phase 7).
3. Assistant cũ là **đường lui bắt buộc** (spec §2, §10): agent tắt, chưa cấu hình service, lệch `contractVersion`,
   router đổi model hay lỗi → app tự rơi về assistant cũ. Gỡ nó đồng nghĩa người dùng chưa cấu hình `AGENT_*` mất
   hẳn trợ lý.

Đề xuất lộ trình: phát hành 1.2.0 → 1.4.0, chạy eval ≥ 2 lần/model, dùng thật ≥ 1 bản. Khi đủ điều kiện, bản gỡ nên
là minor riêng: đổi assistant cũ thành thông báo "hãy bật Trợ lý nâng cao" thay vì xoá route ngay (bản quay về vẫn chạy
được), ghi rõ trong CHANGELOG của bản đó.
