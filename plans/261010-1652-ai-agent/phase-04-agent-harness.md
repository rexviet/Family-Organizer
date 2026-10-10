# Phase 4 — Agent harness: tool đọc, hỏi lại, đề xuất đi chợ

**Priority:** P1 · **Effort:** 10h · **Status:** Done

## Context Links
- Spec §2, §6, §7
- PTC: `src/harness/agent.py` (`_EndWhenSettled` dòng 474, `_refuse_an_unstaged_change` dòng 840, `_codemode` dòng 510), `src/harness/clarifications.py`, `src/harness/outcome.py`
- API đọc: `server.ts` — `GET /api/users`, `/api/tasks`, `/api/plans`, `/api/finance`, `/api/finance/categories`, `/api/finance/budgets`, `/api/finance/recurring-bills`, `/api/shopping`, `/api/shopping/meal-plan/current`
- Bung lịch lặp: `src/utils/recurrence.ts` (`expandRecurringOccurrences`) — **port sang Python, dùng chung test case**

## Overview
Agent thật: 9 tool đọc, `ask_user`, 3 tool đề xuất đi chợ, `EndWhenSettled`, instructions, output validator. Tool đề xuất Việc/Lịch/Thu chi để phase 8–9.

## Key Insights
- Docstring + kiểu trả về **là** giao diện model nhìn thấy (CodeMode sinh stub) → viết tiếng Việt, ghi rõ đơn vị (VND, `YYYY-MM-DD HH:mm`).
- Monty không có `datetime.now()` → ngày hôm nay chỉ đến từ instructions.
- `GET /api/tasks` trả cả `history`, `comments`, `proofImage` → tool phải **cắt** trường; không đưa ảnh/base64 cho model.
- Tool đọc thu chi với con/khách sẽ nhận 403 → chuyển thành lỗi tiếng Việt, không crash lượt.

## Requirements
- `AppDeps` (dataclass, tạo mới mỗi lượt): `http: httpx.AsyncClient` (base `APP_INTERNAL_URL`, header `Authorization: Bearer <agentToken>` — token **ngắn hạn, chỉ đọc** do Node cấp, xem phase 5; event hook từ chối mọi method ≠ GET và path ngoài allowlist 9 endpoint; timeout 10 s), `cache` (mỗi endpoint gọi **tối đa 1 lần/lượt**), `user`, `today`, `weekday`, `members` (lấy 1 lần đầu lượt), `outcome: OutcomeSlot(max=10)`, `clarifications: ClarificationSink`.
- Tool đọc (spec §6.1) — **không nhận id để ghép vào URL** (chỉ gọi route danh sách, lọc phía client); lọc theo tham số; trả TypedDict gọn:
  - `list_tasks` bỏ `comments/history/proofImage/proofNote`; `search_transactions` bỏ `receiptImage`; `list_plans` bung lặp trong `[date_from, date_to]`, tối đa 62 ngày.
- `ask_user(question, options=[])`.
- Đề xuất đi chợ: `propose_add_shopping_items`, `propose_set_purchased`, `propose_remove_shopping_items` → validate (id tồn tại trong `list_shopping`, tên không rỗng, gộp trùng tên không dấu) → `outcome.add(op)` với `base.fingerprint` tính bằng `contract.py`.
- `EndWhenSettled` như PTC; output validator: câu trả lời khẳng định đã làm ("đã thêm|đã xoá|đã tạo|đã cập nhật|đã ghi") mà `outcome` rỗng → `ModelRetry`.
- Instructions (`prompts.py`): vai trò, ngắn gọn tiếng Việt; ngày + thứ + múi giờ; bảng thành viên (id, tên, quan hệ, role); từ điển hạng mục chi; luật đề xuất; "id phải lấy từ tool đọc".
- Giới hạn: `CodeMode(max_tool_calls=40, resource_limits={"max_duration_secs": 15, "max_memory": 134217728})` (bytes; thời lượng tính dồn cho các `run_code` trong một lượt → timeout 90 s của lượt mới là giới hạn thật); `UsageLimits(request_limit=6)`.
- Với `EndWhenSettled`, `result.output` là `None` → `/run` đọc kết quả từ `deps.outcome`/`deps.clarifications`; `result.usage` là thuộc tính (không gọi hàm).
- `/run` trả `answer | proposal | clarification` + `history` (`ModelMessagesTypeAdapter`), cắt còn 20 lượt **chỉ tại ranh giới tin nhắn người dùng** (không để `tool_call` mồ côi → 400). History không parse được (sau nâng cấp thư viện) → bỏ history, không làm hỏng lượt.

## Related Code Files
- Tạo: `agent/src/family_agent/harness/{deps.py, outcome.py, clarify.py, end_when_settled.py, prompts.py, agent.py, recurrence.py}`, `harness/tools/{read.py, shopping.py}`
- Sửa: `agent/src/family_agent/app.py` (gắn agent thật)
- Test: `agent/tests/unit/test_read_tools.py` (mock httpx bằng `respx`), `test_shopping_tools.py`, `test_end_when_settled.py`, `test_recurrence.py` (cùng case với `src/utils/recurrence.test.ts`), `test_run_flow.py` (FunctionModel kịch bản: đọc → đề xuất → End)

## Implementation Steps (TDD — mỗi mục RED trước)
1. `outcome.py`, `clarify.py` + test (giới hạn 10, không trùng).
2. `recurrence.py` port + test dùng chung case.
3. Tool đọc + test mock: lọc, cắt trường, 403 → lỗi tiếng Việt.
4. Tool đi chợ + test: id không tồn tại → `ask_user`; gộp trùng; fingerprint đúng.
5. `EndWhenSettled` + test với `FunctionModel`: sau step có op → `End`, không gửi request thứ 2.
6. Output validator + test.
7. Gắn vào `/run`; test luồng đầy đủ 3 kind.
8. Chạy tay với model thật từ spike (10 câu phase 1) — ghi kết quả vào `reports/`.

## Todo
- [x] Deps/outcome/clarify
- [x] Port recurrence
- [x] 9 tool đọc
- [x] 3 tool đi chợ
- [x] EndWhenSettled + output validator
- [x] /run trả 3 kind + history
- [x] Thử 10 câu với model thật

## Success Criteria
pytest xanh; với model đã chọn ở spike: 10 câu ≥ 7 đúng, không lượt nào ghi dữ liệu.

## Ghi chú từ review phase 3
- `asyncio.timeout` của `/run` chỉ huỷ được ở điểm `await`: nếu `run_code` (Monty) chạy đồng bộ trên event loop thì
  timeout 90 s và `/health` đều treo; nếu qua `to_thread` thì slot trả lại khi luồng còn chạy. Dựa vào
  `resource_limits.max_duration_secs` (< `AGENT_RUN_TIMEOUT_S`) và thêm test: lượt chạy code lâu vẫn 504, `/health` vẫn trả lời.
- `history` trả cho Node chứa cả tool return → `agentToken` chỉ được nằm trong deps/http client, không bao giờ trong
  instructions/tool args/message. Test: sau lượt có gọi tool, `TOKEN not in json.dumps(history)`.

## Risk Assessment
- Model gọi tool bằng tên/kiểu sai → stub rõ + few-shot 2 ví dụ trong instructions.
- `history` phình → cắt 20 lượt theo ranh giới tin nhắn người dùng (không tóm tắt tool return — YAGNI).

## Security Considerations
Token người dùng chỉ sống trong `AppDeps` của lượt đó; không cache giữa người dùng. Tool không có đường ghi nào.

## Next Steps
Phase 5 nối vào; phase 8–9 thêm tool đề xuất.

## Ghi chú triển khai
(Thực hiện 2026-10-10. Báo cáo thử model thật: [reports/phase-04-real-model.md](reports/phase-04-real-model.md) — 3 lần chạy đều 10/10, 0 ghi.)

**Phát hiện Monty (ghi chú review phase 3)**
- Đo bằng test (`test_app.py::test_run_code_chay_vo_han_...`) và probe: `run_code` chạy **ĐỒNG BỘ trên event loop** — một `while True` làm
  event loop đứng đúng ≈ `max_duration_secs` (đo 0.96 s với giới hạn 1 s), `/health` và các lượt khác treo trong lúc đó; `asyncio.timeout` không cắt được vì không có `await`.
- Ngân sách thời gian **tính dồn cho cả lượt** (4 `run_code` × 0.5 s với giới hạn 0.6 s: chỉ cái đầu chạy đủ, các cái sau lỗi ngay) → tổng thời gian treo tối đa của một lượt ≈ `max_duration_secs` (15 s mặc định).
- Sau khi Monty ngắt, model nhận lỗi `TimeoutError` như lỗi tool thường; lượt tiếp tục và bị timeout cứng (504) ở `await` kế tiếp nếu quá `AGENT_RUN_TIMEOUT_S`.
- **ĐÍNH CHÍNH (review):** giới hạn trên chỉ đúng với MỘT phiên. `run_code(restart=true)` cấp lại ngân sách, và nhiều `run_code` trong một phản hồi model chạy nối tiếp không có `await` → đo được 0.95 s treo với giới hạn 0.3 s (3 call); với mặc định (6 call) ≈ 90 s. Đã sửa bằng `harness/code_guard.py` (xem mục "Sửa sau review") — treo liên tục ≤ một ngân sách, cả lượt ≤ ~2 ngân sách.
- Quyết định: **không** đẩy Monty sang thread (client OpenAI dùng chung giữa các event loop dễ hỏng, slot trả lại khi luồng còn chạy). Thay vào đó: `AGENT_CODE_MAX_DURATION_S` (mặc định 15) **bắt buộc < `AGENT_RUN_TIMEOUT_S`** (validator trong `Settings`), tiêm được cho test; stall tối đa 15 s/lượt được chấp nhận (healthcheck Docker cần 3 lần hỏng liên tiếp; app có tối đa 2 lượt đồng thời). Nếu sau này thấy đau → hạ xuống 5–8 s hoặc chạy agent trong process con.
- `run_code` có ngưỡng retry riêng (3, **không** theo `retries["tools"]`): model viết code lỗi liên tục → `UnexpectedModelBehavior` → `/run` 502 `llm_error` (Node fallback assistant cũ, phase 5). Có test.
- Hàm tool nào ném ngoại lệ (kể cả `ModelRetry`) trong CodeMode đều thành "Runtime error … <thông điệp>" cho model, không làm hỏng lượt → mọi lỗi tool dùng `ToolError(ModelRetry)` với câu tiếng Việt.

**Quyết định (ngoài danh sách orchestrator)**
1. Shopping `base` là `{"updatedAt"}` (không `fingerprint`) — theo hợp đồng. Mọi op qua `contract.validate_operations` **ngay lúc thêm** (`OutcomeSlot.add`, lỗi tiếng Việt cho model, ghi tất cả-hoặc-không) và **một lần nữa** ở `/run` (`settle`): sai → trả `answer` "chưa lập được đề xuất hợp lệ", không bao giờ trả proposal sai.
2. Câu hỏi thắng đề xuất: nếu trong cùng lượt vừa có op vừa có câu hỏi, trả `clarification`, bỏ op (người dùng chưa thấy op).
3. Shopping: món đã có trong danh sách **chưa mua** (so không dấu) → bỏ qua và báo model; món đã mua rồi → vẫn thêm (mua lại). `shopping.add` tách mỗi op ≤ 20 món; tổng ≤ 30 (lỗi tiếng Việt). id lạ ở `set_purchased/remove` → `ask_user`-style (câu hỏi không lộ id nội bộ, `options` = tên các món gợi ý), cả lần gọi không ghi gì; món đã ở đúng trạng thái → bỏ qua.
4. `items` của `propose_add_shopping_items` nhận `str` hoặc `{name, quantity?, note?}` (model hay đưa chuỗi).
5. Tool đọc: client HTTP chặn thêm query string và host lạ (chống rò token qua URL tuyệt đối); `follow_redirects=False`; lỗi cũng được cache (1 request/endpoint/lượt). 401 hoặc lỗi lấy thành viên → vẫn chạy lượt, ghi chú trong instructions, tool tự báo lỗi.
6. Hạng mục chi: từ điển mặc định (11 mục, nhãn vi.json) viết sẵn trong instructions; hạng mục tự thêm → model gọi `list_expense_categories` (không prefetch vì con/khách bị 403). `search_transactions(category=)` nhận id hoặc nhãn mặc định.
7. `list_tasks` thêm cờ `overdue` tính bằng code (status stale) và `status="open"|"overdue"`; `list_plans`: sự kiện không lặp nhiều ngày = MỘT dòng với `date` = ngày bắt đầu (có thể trước `date_from` khi đang diễn ra).
8. Recurrence: giữ y nguyên guard 400 vòng lặp và cả hành vi cuộn ngày của `new Date(y, m-1, d)` (31/02 → 03/03; năm 0–99 → 19xx). Case dùng chung ở `src/utils/recurrence.cases.json`; `recurrence.test.ts` chuyển thành data-driven (36 case, gồm các case cũ + Chủ nhật/getDay, guard 400, 29/02, endDate hỏng, from>to).
9. History: bỏ `instructions` khỏi mọi request trước khi trả (dựng lại mỗi lượt, tránh phình); lượt kết thúc bằng đề xuất/câu hỏi được thêm một `ModelResponse(TextPart(reply))` do code dựng để lượt sau có ngữ cảnh. Vượt `request_limit` → `answer` "hỏi gọn hơn", history = cũ + câu hỏi + câu trả lời này.
10. Output validator bắt "đã thêm|xoá|xóa|tạo|cập nhật|ghi" (so trên chuỗi bỏ dấu); `retries={"tools": 1, "output": 2}`; vượt → 502 như lỗi model.
11. `/run` JSON: `reply` có ở mọi kind (clarification: `reply` = `question`); `operations` chỉ ở proposal; `question/options` chỉ ở clarification.
12. Thêm biến `AGENT_CODE_MAX_DURATION_S`; thêm `http_transport` (chỉ test) vào `create_app`; `extend-exclude = ["spike"]` cho ruff (spike đã chốt, vốn có 21 lỗi lint); `eval/` vào `.dockerignore`; thêm `respx` vào nhóm dev.
13. File thêm ngoài danh sách: `harness/vocab.py` (nhãn quan hệ/hạng mục, `fold` bỏ dấu), `harness/tools/ask.py`, `tests/unit/test_deps.py`, `test_prompts.py`, `eval/phase4_smoke.py`.

**Lệch TDD:** `end_when_settled.py` được viết ngay trước lần chạy test đầu của nó (chuỗi lệnh bị ngắt giữa chừng) — test đã được kiểm lại độc lập sau đó; các test `/run` 3-kind ở `test_app.py` viết sau code vì chỉ nối các phần đã có test riêng.

## Sửa sau review (7.5/10)
- **H1** `harness/code_guard.py` (capability bao `run_code`): một `run_code` mỗi phản hồi model (các cái sau bị từ chối, bảo model gộp bằng `asyncio.gather`); từ chối `restart`; cộng dồn thời gian THẬT (wall-clock, kể cả chờ HTTP trong code — bảo thủ, nên app chậm có thể hết ngân sách sớm) và hết `code_max_duration_s` thì từ chối `run_code` bằng câu cố định. Test tái hiện 3 call × 3 phản hồi có restart: stall liên tục ≤ ngân sách + 0.25 s, tổng ≤ 2 ngân sách (test đỏ khi bỏ CodeGuard).
- **H2** Validator tách hai mẫu: ngôi thứ nhất (`mình|tôi|em đã|vừa` + thêm/xoá/xóa/tạo/cập nhật/ghi/đánh dấu/mua/sửa/giao — chạy trên chuỗi CÒN dấu vì "Mình" khác tên "Minh") và đứng trần (đầu câu/dòng hoặc sau ok/vâng/rồi/được/xong + đã thêm/xoá/xóa/tạo/cập nhật/ghi). Câu đọc ngôi thứ ba ("Mẹ đã ghi 3 khoản…", "Các món đã mua:") không bị bắt. `UnexpectedModelBehavior` (hết output retries, `run_code` lỗi quá 3 lần) → `answer` thân thiện + history tổng hợp, không còn 502; 502 chỉ còn cho lỗi LLM/endpoint thật.
- **M1** Rollback theo `run_code`: lỗi giữa chừng → trả `outcome` và `clarifications` về trước lần chạy, lượt không kết thúc, model nhận lỗi và thử lại (cơ chế đơn giản nhất; nếu code của model tự `try/except` lỗi thì không hoàn tác — chủ ý của model).
- **M2** Mỗi món chỉ một thay đổi/lượt (set_purchased+delete, true rồi false → `ToolError`; kiểm trên mọi món được nêu kể cả món đã ở đúng trạng thái; đề xuất y hệt thì bỏ qua). `shopping.add` bỏ tên đã đề xuất trước đó trong lượt (so không dấu) và báo.
- **M3** `_int` nhận chuỗi số ("50000"), số thực làm tròn bằng `round` (.5 về chẵn), NaN/vô cực/chuỗi hỏng → 0.
- **M4** `TurnLimits.max_history_bytes = 1_000_000`: sau khi cắt 20 lượt, còn lớn hơn thì bỏ nguyên lượt cũ nhất tới khi vừa (luôn giữ lượt cuối). Không cắt nội dung tool-return cũ (bỏ qua có chủ ý: tool return của CodeMode vốn nhỏ vì code tự tổng hợp; cắt giữa chừng dễ làm hỏng ngữ cảnh) — thêm nếu thực tế thấy history phình.
- **L1** cache: `asyncio.shield` + loại task đã huỷ; `AppDeps.aclose()` huỷ request còn bay và lấy ngoại lệ trước khi đóng client. **L2** phản hồi từ app đọc theo stream, > 20 MB (`MAX_RESPONSE_BYTES`) → lỗi tiếng Việt. **L3** `recurrenceWeekdays` không phải list → thứ mặc định (Python-only; bản TS tự xử lý chuỗi theo kiểu JS). **L4** `search_transactions(category=)` nhận thêm nhãn hạng mục tự thêm (tra `/api/finance/categories` khi không phải id/nhãn mặc định). **L6** `APP_INTERNAL_URL` có path khác gốc bị từ chối ở `Settings`. **L7** `load_history` bỏ `SystemPromptPart` (và request chỉ còn system prompt).

## Sửa sau re-review (8.5/10)
- **Rollback khi code tự bắt lỗi:** `propose_*`/`ask_user` bọc trong `flag_failures(deps)` → đặt `deps.tool_failed`; cuối mỗi `run_code`, cờ bật thì hoàn tác dù code "thành công" rồi `ModelRetry`. (Hook `on_tool_execute_error` của capability KHÔNG chạy cho tool con gọi từ sandbox nên không dùng được.) Test: `try/except` quanh add 31 món sau remove → không ra proposal.
- **Model biết đã hoàn tác:** lỗi/rollback kèm câu "Mọi đề xuất/câu hỏi trong lần chạy này đã bị HUỶ; hãy gọi lại đầy đủ." (chỉ khi thật sự có gì bị hoàn tác). Validator thêm "đề xuất" vào mẫu ngôi thứ nhất.
- `Settings`: bắt buộc `2 × AGENT_CODE_MAX_DURATION_S < AGENT_RUN_TIMEOUT_S`. Validator chuẩn hoá NFC trước mẫu có dấu (test NFD).
- Chỉ "hết retry" (`max… retries` trong thông điệp: output validator, `run_code` quá 3 lần) → answer thân thiện; `ContentFilterError`, phản hồi rỗng/sai định dạng và mọi `UnexpectedModelBehavior` khác → re-raise → 502. Lớp có trong pydantic-ai 2.33: `UnexpectedModelBehavior`, `ContentFilterError`, `IncompleteToolCall`, `UsageLimitExceeded` (xử lý riêng). Nhận diện hết-retry bằng thông điệp nên nhạy với nâng cấp thư viện (có test hai chiều).
