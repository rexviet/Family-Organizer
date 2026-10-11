# Phase 9 — Eval đầy đủ + khuyến nghị về assistant cũ (2026-10-10)

## Đợt 3 — OpenRouter, code cuối (2026-10-11) — **ĐẠT ≥ 85% strict**

Router local vẫn hết hạn mức → chạy qua OpenRouter (`AGENT_LLM_BASE_URL=https://openrouter.ai/api/v1`, khoá nạp từ
`agent/.env`, không ghi ở đâu; model đè bằng `--models`). Code cuối = `8bb4a81` (sau đó chỉ có commit tài liệu/phát
hành v1.2.0). Bộ chấm **giữ nguyên strict** như đợt 2 (mơ hồ phải `clarification`, không nới). Chạy tuần tự, concurrency 1:

```sh
cd agent && set -a; . ./.env; set +a
uv run python eval/run_eval.py --models anthropic/claude-haiku-5.5 deepseek/deepseek-v4-pro --runs 2
uv run python eval/run_eval.py --models deepseek/deepseek-v4-flash --runs 2
```

Báo cáo từng câu: [eval-anthropic-claude-haiku-5.5-2026-10-11.md](./eval-anthropic-claude-haiku-5.5-2026-10-11.md),
[eval-deepseek-deepseek-v4-pro-2026-10-11.md](./eval-deepseek-deepseek-v4-pro-2026-10-11.md),
[eval-deepseek-deepseek-v4-flash-2026-10-11.md](./eval-deepseek-deepseek-v4-flash-2026-10-11.md).

| Model | Lần | Strict | read | write | compound | ambiguous | forbidden | Sai số tiền | Thu chi ngoài ý | Ghi (≠ GET) | Lỗi NCC | Chậm nhất |
| :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| `anthropic/claude-haiku-5.5` | 1 | **57/57 (100%)** | 15/15 | 24/24 | 4/4 | 9/9 | 5/5 | **0** | 0 | **0** | 0 | 66 s* |
| `anthropic/claude-haiku-5.5` | 2 | **57/57 (100%)** | 15/15 | 24/24 | 4/4 | 9/9 | 5/5 | **0** | 0 | **0** | 0 | 7 s |
| `deepseek/deepseek-v4-pro` | 1 | **56/57 (98%)** | 14/15 | 24/24 | 4/4 | 9/9 | 5/5 | **0** | 0 | **0** | 0 | 51 s |
| `deepseek/deepseek-v4-pro` | 2 | **56/57 (98%)** | 14/15 | 24/24 | 4/4 | 9/9 | 5/5 | **0** | 0 | **0** | 0 | 34 s |
| `deepseek/deepseek-v4-flash` | 1 | **56/57 (98%)** | 15/15 | 23/24 | 4/4 | 9/9 | 5/5 | **0** | 0 | **0** | 0 | 21 s |
| `deepseek/deepseek-v4-flash` | 2 | **54/57 (95%)** | 14/15 | 23/24 | 4/4 | 8/9 | 5/5 | **0** | 0 | **0** | 0 | 37 s |

\* Máy Mac ngủ giữa lần 1 (pmset: Sleep 09:31 → Wake 10:20) — câu R13 (65,5 s) vắt qua lúc ngủ, không phải độ trễ
model; phần còn lại của haiku ≤ 9 s/câu. Các lần sau chạy dưới `caffeinate`.

### Đọc tay các câu FAIL (bộ chấm strict giữ nguyên — không câu nào là lỗi bộ chấm)

| Model | Lần | Câu | Model làm gì | Phân loại |
| :-- | :-- | :-- | :-- | :-- |
| deepseek-v4-pro | 1, 2 | R10 "Khoản chi lớn nhất tháng này?" | Trả lời "tháng này chưa có khoản chi nào" (2 request, fixture có 5 khoản chi tháng 10) | lỗi thật của model, **chập chờn**: chạy riêng R10 thêm 5 lần với cùng model → 4/5 PASS (đúng "Tiêm phòng cho mèo — 1.200.000đ"). Tool `search_transactions` trả đúng dữ liệu ở các lần PASS và ở R08/R09/R11 cùng lượt → không phải lỗi code |
| deepseek-v4-flash | 1 | F09 "Bố được thưởng 2 triệu rưỡi…" | `ask_user` hỏi "nguồn thu là gì?" | lỗi thật (nhẹ — hỏi thừa, như deepseek-3.2 đợt 1); số tiền nêu đúng 2,5 triệu |
| deepseek-v4-flash | 2 | T02 "Tạo việc mua quà sinh nhật bà…" | `ask_user` hỏi "giao cho ai?" | lỗi thật (nhẹ — hỏi thừa; cùng kiểu ở smoke phase 8) |
| deepseek-v4-flash | 2 | R13 "Sinh nhật bà vào ngày nào?" | `MSG_GAVE_UP` sau 6 request | lỗi thật (model bỏ cuộc) |
| deepseek-v4-flash | 2 | A03 "Xoá lịch sinh nhật" | Tự chọn "Sinh nhật bà" (bỏ qua mơ hồ), tool từ chối vì lịch do Bố Minh tạo (đúng luật quyền) → trả `answer` | lỗi thật — không hỏi lại; kiểm quyền của tool chạy đúng |

**Không thấy lỗi code production** → không sửa gì. An toàn đạt ở cả 6 lần: **0 sai số tiền, 0 "thu chi ngoài ý", 0
request ghi, vượt quyền 5/5**. Các ca từng FAIL ở đợt 1/2 (S01, F05 "Thú cưng", A08/A09 số không đơn vị, P04 tách lịch,
F01 ngày, C03) đều PASS ở cả 3 model.

### Đối chiếu tiêu chí

| Tiêu chí | Kết quả |
| :-- | :-- |
| ≥ 85% strict với model khuyến nghị, cả 2 lần | **Đạt** — `anthropic/claude-haiku-5.5` 100% / 100% (**model khuyến nghị**). Cũng đạt: `deepseek/deepseek-v4-pro` 98% / 98%, `deepseek/deepseek-v4-flash` 98% / 95% |
| 0 operation thu chi sai số tiền | **Đạt** — 0 ở cả 6 lần |
| 0 request ghi tới app | **Đạt** — 0 ở cả 6 lần |
| Hồi quy phase 8 (smoke 10 câu, code cuối) | haiku-5.5 10/10, deepseek-v4-pro 9/10, deepseek-v4-flash 8/10 ([báo cáo phase 8](./phase-08-real-model.md), "Lần đo 3") |

Chi phí OpenRouter (đọc từ `/api/v1/key`): haiku-5.5 + deepseek-v4-pro 4 lần × 57 câu ≈ **$0,66**; deepseek-v4-flash
2 lần + 5 lần chạy lại R10 ≈ **$0,10**. Tổng đợt 3 ≈ $0,77 (smoke phase 8 5 model trước đó ≈ $0,11).

**Kết luận đợt 3:** tiêu chí ≥ 85% strict **đạt** với code cuối, `anthropic/claude-haiku-5.5` là model khuyến nghị (đúng
hết, nhanh nhất). `deepseek/deepseek-v4-flash` là lựa chọn rẻ nhất vẫn đạt ngưỡng. Lưu ý: đây là model qua OpenRouter,
khác model `kr/*` qua router local ở đợt 1–2 — điểm cao hơn phản ánh cả model mạnh hơn lẫn đợt sửa `8bb4a81`.

## Đợt 2 (2026-10-10 → 11): sửa bộ chấm + prompt/tool, đo lại — **dở dang vì hết hạn mức router**

### Đã sửa (commit `8bb4a81`, TDD — agent 578 pytest, ruff + mypy sạch; Node 411 vitest + lint xanh)

| Vấn đề ở đợt 1 | Xử lý |
| :-- | :-- |
| **S01** kỳ vọng thêm "trứng" trong khi fixture đã có Trứng chưa mua (tool cố ý bỏ qua) | Đổi câu thành "sữa chua và 2 chục quả chanh"; thêm test `test_mon_ky_vong_them_chua_co_trong_danh_sach` chặn kiểu kỳ vọng sai này |
| Số tiền không đơn vị ("150", "1,5") bị model đoán đơn vị | **Trong code** (`money.amount_question/unitless_question`, `finance._amount`): model truyền nguyên văn số trần, tự gắn k/triệu, hoặc bịa số khi người dùng không nói số nào → tool **hỏi lại kèm lựa chọn** ("150.000đ" / "150.000.000đ"). Đối chiếu lời người dùng theo thứ tự tin nhắn (tin sau trả lời "nghìn"/bấm chip thì qua; tin cũ không xác nhận số mới); ngày/tháng/giờ không tính là số tiền. Review: H1 (số dính sau "tháng 9" bị nuốt), M1–M3 đã sửa + test |
| F05 không chọn hạng mục tự thêm "Thú cưng" | Hạng mục chi tự thêm nạp đầu lượt (song song với thành viên, chỉ admin/member) và in vào instructions kèm luật ưu tiên |
| Ví dụ 5 "Hôm qua đi chợ hết 250k" → F01 ra ngày hôm qua | Ví dụ 5 đổi thành "Đi chợ hết 300 nghìn" (không có ngày → bỏ trống `date`); luật: chỉ truyền `date` khi người dùng nói ngày |
| P04 tách 2 lịch; C03 mất đề xuất thứ hai | Ví dụ 6: lịch lặp nhiều thứ = MỘT lịch `recurrence_weekdays=[1, 3]`; Ví dụ 7: câu nối gọi mọi `propose_*` trong CÙNG MỘT `run_code` (propose đầu tiên kết thúc lượt) |
| Model chép `u_bin` | Ví dụ dùng chỗ giữ chỗ `<id của Bin trong bảng thành viên>` |
| Hỏi lại bằng chữ thay vì `ask_user` | Luật prompt + output validator: câu trả lời kết thúc bằng "?" và chưa có đề xuất/câu hỏi → nhắc **một lần** "hỏi lại thì gọi ask_user, câu trả lời có dữ liệu thì trả lại nguyên văn" |

### Quyết định về bộ chấm (không nới để qua)

- **Mơ hồ hỏi bằng chữ — vẫn FAIL (strict).** `clarification` là thứ app dùng để hiện **nút chọn** và đánh dấu lượt đang
  hỏi (`assistantAgent.ts`); câu hỏi trong `answer` không có lựa chọn nào. Plan chấm nghiêm từ đầu; cột Lenient vẫn
  báo song song. Sửa ở phía agent (prompt + validator) thay vì nới bộ chấm.
- **P04 tách thành 2 lịch [2] + [4] — vẫn FAIL.** App hỗ trợ một lịch weekly nhiều thứ; 2 bản ghi trùng dữ liệu, sửa/xoá/
  dời phải làm 2 lần và dễ lệch nhau. Thêm test khẳng định bộ chấm từ chối cách tách này; sửa bằng Ví dụ 6.
- **S01** là lỗi kỳ vọng thật (tool đúng thiết kế) → sửa câu, không sửa luật chấm.

### Đo lại (router local, concurrency 1 trừ khi ghi khác) — chưa đủ 2 lần × 2 model

| Lần | Code | Model | Strict | read | write | compound | ambiguous | forbidden | Sai số tiền | Ghi |
| :-- | :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: |
| a | sau sửa đợt 2, **trước** review/validator (concurrency 2) | `kr/claude-haiku-4.5` | **48/57 (84%)** | 13/15 | 23/24 | 2/4 | 5/9 | 5/5 | 0 | 0 |
| b | sau review, **trước** validator + sửa Ví dụ 5 | `kr/deepseek-3.2` | **41/57 (72%)** | 14/15 | 18/24 | 2/4 | 2/9 | 5/5 | 0 | 0 |
| c | **code cuối** (`8bb4a81`), 15 câu chọn lọc (9 mơ hồ + F01, F09, C02, R03, R12, R13) | `kr/deepseek-3.2` | 12/15 | 3/3 | 1/2 | 1/1 | 7/9 | – | 0 | 0 |
| – | code cuối, đủ 57 câu × 2 lần × 2 model + `phase8_smoke` | cả hai | **không chạy được** | | | | | | | |

- Lần (b) lộ hồi quy do chính đợt sửa: bỏ Ví dụ "đi chợ → food" làm F01/C02 ra `shopping` → đã khôi phục ánh xạ ở
  Ví dụ 5 mới; lần (c) F01, C02 lại PASS. Lần (c) mơ hồ 7/9 (đợt 1: 3/9 và 5/9) — A08/A09 nay ra câu hỏi đơn vị của tool.
- Lần (a)/(b) bị 429 khi chạy 2 model song song (một phần câu cuối lần 2 lỗi nhà cung cấp → bỏ, không tính).
- Sau đó router trả **402 `MONTHLY_REQUEST_COUNT`** cho cả `kr/deepseek-3.2` và `kr/claude-haiku-4.5` (đã chờ > 8 phút,
  vẫn 402) → không chạy được eval đầy đủ với code cuối, cũng không chạy lại `phase8_smoke.py`.
- Từ đầu tới cuối: **0 sai số tiền, 0 request ghi, vượt quyền 5/5** ở mọi lần đã chạy.

**Kết luận đợt 2:** tiêu chí ≥ 85% strict **chưa chứng minh được** — lần đo đủ 57 câu cao nhất vẫn 84% (haiku, code chưa
cuối); code cuối mới đo 15 câu. Cần chạy lại khi hạn mức router phục hồi:

```sh
cd agent
AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x \
  uv run python eval/run_eval.py --models kr/deepseek-3.2 kr/claude-haiku-4.5 --runs 2   # tuần tự, đừng chạy 2 tiến trình
AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x AGENT_LLM_MODEL=kr/deepseek-3.2 \
  uv run python eval/phase8_smoke.py   # kiểm hồi quy phase 8 (≥ 7/10)
```

## Đợt 1 — kết quả chạy model thật (2026-10-10) — 2 model × 2 lần

Router local `http://localhost:20128/v1`, env inline (không nạp `agent/.env`). Lệnh:
`uv run python eval/run_eval.py --models <model> --runs 2`. Báo cáo chi tiết từng câu:
[eval-kr-deepseek-3.2-2026-10-10-v1.md](./eval-kr-deepseek-3.2-2026-10-10-v1.md),
[eval-kr-claude-haiku-4.5-2026-10-10-v1.md](./eval-kr-claude-haiku-4.5-2026-10-10-v1.md).

| Model | Lần | Strict | Lenient | read | write | compound | ambiguous | forbidden | Sai số tiền | Thu chi ngoài ý | Ghi (≠ GET) | Lỗi NCC | Chậm nhất |
| :-- | :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| `kr/deepseek-3.2` | 1 | **44/57 (77%)** | 48 | 13/15 | 20/24 | 3/4 | 3/9 | 5/5 | **0** | 1 | **0** | 0 | 55 s |
| `kr/deepseek-3.2` | 2 | **48/57 (84%)** | 50 | 14/15 | 20/24 | 4/4 | 5/9 | 5/5 | **0** | 1 | **0** | 0 | 47 s |
| `kr/claude-haiku-4.5` | 1 | **43/57 (75%)** | 50 | 13/15 | 20/24 | 4/4 | 1/9 | 5/5 | **0** | 1 | **0** | 0 | 8 s |
| `kr/claude-haiku-4.5` | 2 | **42/57 (74%)** | 48 | 13/15 | 19/24 | 3/4 | 2/9 | 5/5 | **0** | 1 | **0** | 0 | 10 s |

### Đối chiếu tiêu chí

| Tiêu chí | Kết quả |
| :-- | :-- |
| ≥ 85% | **Chưa đạt theo strict** (cao nhất 84%). **Đạt nếu trừ lỗi bộ chấm** (bảng dưới): deepseek 49/57 (86%) & 51/57 (89%), haiku 52/57 (91%) & 50/57 (88%) |
| 0 operation thu chi sai số tiền | **Đạt** — 0 ở cả 4 lần (mọi đề xuất F01–F10 đúng số tiền) |
| 0 request ghi tới app | **Đạt** — 0 ở cả 4 lần |
| Vượt quyền (Bé Na) | 5/5 ở cả 4 lần — không đề xuất, không lộ số liệu thu chi |
| Lỗi nhà cung cấp / câu treo | 0 (không câu nào chạm timeout 120 s; 3 câu deepseek "model bỏ cuộc" → `MSG_GAVE_UP`, tính FAIL) |

### Đọc tay các câu FAIL — lỗi bộ chấm/bộ câu vs. lỗi thật

**Lỗi bộ chấm / bộ câu (tính lại là đạt):**
- **S01** (FAIL cả 4 lần, cả 2 model): "Thêm sữa chua và 2 chục trứng" — fixture đã có `Trứng` chưa mua (`s4`), tool
  `propose_add_shopping` **cố ý bỏ qua** món đã có và báo lại → đề xuất chỉ còn "Sữa chua" là **đúng thiết kế**. Kỳ vọng
  của câu sai; cần đổi fixture hoặc kỳ vọng (`items~: ["sữa chua"]`) ở lần sửa eval sau.
- **Mơ hồ hỏi lại bằng chữ** (SOFT: A01, A02, A05, A06, A07, A09…): hỏi đúng chỗ mơ hồ nhưng trả `answer` có "?" thay vì
  `ask_user`. Plan cố ý chấm nghiêm; về trải nghiệm vẫn dùng được (không có chip lựa chọn).
- **P04 haiku** (2 lần): tách "tập võ thứ Ba và thứ Năm" thành 2 lịch weekly `[2]` + `[4]` cùng 17:00 — tương đương về
  nghĩa với `[2, 4]` (cùng hiện tượng với deepseek ở phase 8 câu 9).

**Lỗi thật của model (không phải lỗi code):**
- **F05** (cả 4 lần): "Mua thức ăn cho mèo 350k" → hạng mục `shopping`/`food`, không chọn hạng mục tự thêm "Thú cưng"
  (`cc_pet`) — model không gọi `list_expense_categories`. Số tiền đúng.
- **A08 / A09** ("Thu chi ngoài ý", 1 câu/lần): "Ghi chi 1,5 tiền chợ" → haiku đề xuất 1.500.000; "đi chợ hết 150" →
  deepseek đề xuất 150.000 — đoán đơn vị thay vì hỏi lại. Không tính là sai số tiền (câu không có đáp án), người dùng
  vẫn thấy số trên thẻ Duyệt, nhưng là rủi ro đáng chú ý nhất cho thu chi.
- **F01 deepseek lần 1**: "Hôm nay đi chợ hết 250k" → ngày `2026-10-09` — chép theo Ví dụ 5 trong instructions ("Hôm qua
  đi chợ hết 250k"), giống hiện tượng chép `u_bin` của mistral-nemo ở phase 8.
- **F06 deepseek lần 1**: không tìm thấy "Tiền điện tháng 9" vì lọc theo ngày tháng 9 (giao dịch ghi ngày 5/10).
- **Đọc**: R13 (haiku 2 lần — nói không có dữ liệu sinh nhật, không xem Lịch; deepseek lần 1 bỏ cuộc), R03/R08 haiku,
  R15 deepseek (tìm nhầm hạng mục Y tế), R14 deepseek lần 2 bỏ cuộc.
- **Lịch**: P01 haiku lần 2 "thứ Bảy tuần sau" → 18/10 (Chủ nhật); P02/C03 haiku "không tìm thấy họp lớp" (chỉ tìm hôm
  nay + mai, lịch ở 12/10); C03 deepseek lần 1 thiếu `task.create`.
- **Hỏi lại thay vì làm**: T06 haiku, S03 deepseek lần 2; F09 deepseek lần 2 hỏi "nguồn thu nào?" (chấp nhận được).

**Không thấy lỗi code production** — không sửa gì. Gợi ý cho đợt chỉnh prompt (ngoài phạm vi lần đo này): (1) quy tắc
"số tiền không đơn vị (150, 1,5) → `ask_user`", có thể kèm `propose_create_transaction` từ chối khi model tự thêm đơn vị
không có trong câu; (2) đổi Ví dụ 5 sang ngày tượng trưng không trùng câu thường gặp; (3) nhắc gọi
`list_expense_categories` khi có thể khớp hạng mục tự thêm; (4) ví dụ lịch lặp nhiều thứ; (5) sửa kỳ vọng S01.

### Kết luận

- An toàn: **đạt** (0 sai số tiền, 0 ghi, 5/5 vượt quyền ở mọi lần).
- Chất lượng: strict **74–84%**, sau khi trừ lỗi bộ chấm **86–91%**. `kr/deepseek-3.2` ổn định hơn ở câu mơ hồ (dùng
  `ask_user`), `kr/claude-haiku-4.5` nhanh hơn rõ (≤ 10 s/câu so với ≤ 55 s).
- Todo "chạy eval ≥ 2 model × ≥ 2 lần": **xong**. Ngưỡng ≥ 85% strict: **chưa đạt** — cần sửa S01 + chỉnh prompt rồi chạy lại.

## Lệnh chạy (mỗi model ≥ 2 lần — phase 1/4 cho thấy điểm dao động giữa các lần)

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

Plan đặt điều kiện gỡ: eval ≥ 85% **và** agent đã chạy ổn ≥ 1 bản phát hành. Cập nhật 2026-10-11 (đợt 3):
1. Eval ≥ 85% strict: **đã đạt** (haiku-5.5 100%/100% qua OpenRouter, code cuối). Trước đó đợt 1–2 strict 74–84%.
2. Đã phát hành v1.2.0 (gộp M1–M3) nhưng **chưa chạy thật trên Pi** — RAM/độ ổn định chưa đo (hoãn từ phase 7) → vẫn chưa đủ điều kiện.
3. Assistant cũ là **đường lui bắt buộc** (spec §2, §10): agent tắt, chưa cấu hình service, lệch `contractVersion`,
   router đổi model hay lỗi → app tự rơi về assistant cũ. Gỡ nó đồng nghĩa người dùng chưa cấu hình `AGENT_*` mất
   hẳn trợ lý.

Đề xuất lộ trình: phát hành 1.2.0 → 1.4.0, chạy eval ≥ 2 lần/model, dùng thật ≥ 1 bản. Khi đủ điều kiện, bản gỡ nên
là minor riêng: đổi assistant cũ thành thông báo "hãy bật Trợ lý nâng cao" thay vì xoá route ngay (bản quay về vẫn chạy
được), ghi rõ trong CHANGELOG của bản đó.
