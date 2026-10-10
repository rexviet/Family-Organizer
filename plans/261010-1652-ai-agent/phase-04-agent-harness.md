# Phase 4 — Agent harness: tool đọc, hỏi lại, đề xuất đi chợ

**Priority:** P1 · **Effort:** 10h · **Status:** Pending

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
- [ ] Deps/outcome/clarify
- [ ] Port recurrence
- [ ] 9 tool đọc
- [ ] 3 tool đi chợ
- [ ] EndWhenSettled + output validator
- [ ] /run trả 3 kind + history
- [ ] Thử 10 câu với model thật

## Success Criteria
pytest xanh; với model đã chọn ở spike: 10 câu ≥ 7 đúng, không lượt nào ghi dữ liệu.

## Risk Assessment
- Model gọi tool bằng tên/kiểu sai → stub rõ + few-shot 2 ví dụ trong instructions.
- `history` phình → cắt 20 lượt theo ranh giới tin nhắn người dùng (không tóm tắt tool return — YAGNI).

## Security Considerations
Token người dùng chỉ sống trong `AppDeps` của lượt đó; không cache giữa người dùng. Tool không có đường ghi nào.

## Next Steps
Phase 5 nối vào; phase 8–9 thêm tool đề xuất.
