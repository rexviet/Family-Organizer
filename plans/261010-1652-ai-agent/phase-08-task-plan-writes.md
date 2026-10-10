# Phase 8 — Ghi Việc + Lịch (M2)

**Priority:** P2 · **Effort:** 6h · **Status:** Code done — chờ người dùng phát hành 1.3.0 (sau 1.2.0); thử 10 câu model thật hoãn (router LLM local không chạy)

## Context Links
- Spec §6.2 (Việc, Lịch), §9
- `server.ts`: `POST /api/tasks` (luật con/khách ~dòng 911, optimistic lock `hasEditConflict`), `DELETE /api/tasks/:id`, `POST/DELETE /api/plans` (chỉ người tạo hoặc admin)
- `src/types.ts`: `Task` (có `updatedAt`), `FamilyPlan` (**không** có `updatedAt` → guard bằng `fingerprint`)

## Overview
Thêm 6 tool đề xuất + bật 6 loại operation ở apply/preview. Hợp đồng đã có từ phase 2 nên không đổi schema.

## Requirements
- Agent: `propose_create_task`, `propose_update_task`, `propose_delete_task`, `propose_create_plan`, `propose_update_plan`, `propose_delete_plan`.
  - Validate: `assignee_id` thuộc `members`; `due/start/end` đúng định dạng, `end ≥ start`; update phải có ≥ 1 thay đổi thật (so với bản ghi đọc được); `base` lấy từ bản ghi: `updatedAt` (việc) / `fingerprint` (lịch).
  - Tên việc/lịch khớp nhiều bản ghi → `ask_user` với tối đa 5 lựa chọn.
  - Không cho đổi `rewardPoints` của việc đã hoàn thành, không duyệt/trả việc của trẻ.
- Node: `permissions.ts` thêm `canCreateTask/canEditTask/canDeleteTask/canCreatePlan/canEditPlan/canDeletePlan` (khoá hành vi endpoint gốc — **sau** bản vá `comments` ở phase 5 — bằng test trước khi tách); apply qua `applyBatch` với **merge** `{...cũ, ...changes}` (không để trường thiếu thành mặc định); guard `updatedAt` (task) / `fingerprint` (plan). `status:"completed"` bị từ chối từ hợp đồng.
- Preview: `✅ Tạo việc …`, `✏️ Việc "…": hạn 10/10 → 12/10`, `🗑️ Xoá lịch …` (đỏ).
- Instructions: thêm ví dụ dời lịch, giao việc.

## Related Code Files
- Tạo: `agent/src/family_agent/harness/tools/{tasks.py, plans.py}` + test
- Sửa: `server/permissions.ts`, `server/agentApply.ts`, `server/agentPreview.ts`, `server.ts` (endpoint task/plan gọi permissions), test tương ứng; `prompts.py`; CHANGELOG `1.3.0`

## Implementation Steps (TDD)
1. Test khoá luật quyền hiện tại của endpoint task/plan → tách vào `permissions.ts`.
2. Tool Python + test (mơ hồ → hỏi lại; update rỗng → từ chối; base đúng).
3. Apply + preview + test (guard lệch → 409; con sửa việc người khác → 403; member xoá lịch admin → 403).
4. Thử tay 10 câu Việc/Lịch; phát hành M2 (hỏi trước khi push tag).

## Todo
- [x] permissions task/plan (`canCreateTask/canDeleteTask/canCreatePlan/canEditPlan/canDeletePlan`; `canEditTask` có sẵn) — khoá ma trận endpoint gốc bằng test, `server.ts` POST/DELETE /api/plans gọi hàm mới
- [x] 6 tool đề xuất (`tools/tasks.py`, `tools/plans.py`, phần chung `tools/records.py`) + ví dụ giao việc/dời lịch trong instructions
- [x] apply + preview 6 loại (mutator dùng chung trong `dataMutations.ts`; FamilyDB tạo/xoá việc, tạo/sửa/xoá lịch gọi lại cùng mutator)
- [ ] thử 10 câu Việc/Lịch với model thật — đã chạy qua OpenRouter (2026-10-10, [báo cáo](./reports/phase-08-real-model.md)) nhưng **chưa đo được**: `gemma-4-26b-a4b-it:free` 429 upstream liên tục (9/10 câu ở lượt 1); `mistral-nemo` 0/10 × 2 lượt vì không gọi tool (đối chứng phase 4 cũng 0 tool call) — lỗi model, không phải code; 0 request ghi. Cần chạy lại với model gọi tool tốt (deepseek-3.2 / claude-haiku-4.5) trước khi phát hành
- [ ] phát hành 1.3.0 — CHANGELOG đã nháp; **chờ người dùng phát hành** (sau 1.2.0)

## Kết quả (2026-10-10)
- Node: `npm run lint` + `npm test` (390 test) + `npm run build` xanh. Mới: `agentApply.tasks.test.ts` (32 ca: merge, guard 409, quyền 403, ngày/thứ lặp 422, trộn 3 module 1 lần ghi), ma trận quyền ở `permissions.test.ts`, tích hợp SQLite thật ở `db.batch.test.ts`.
- Agent: `uv run pytest` 395 xanh (46 ca mới `test_task_plan_tools.py`), ruff + mypy strict sạch.

## Quyết định (--auto)
- Trợ lý **từ chối** (403) thay vì lặng lẽ bỏ trường như endpoint: Con/Khách đặt `rewardPoints`; Con được giao (không phải người tạo) sửa ngoài `status` — để thẻ Duyệt không hiển thị điều sẽ không xảy ra.
- Không sửa việc đang **chờ duyệt**; không đổi **trạng thái** việc đã hoàn thành (mở lại = reset bằng chứng → làm trong app).
- Một bản ghi xuất hiện hai lần trong một đề xuất → 422 `invalid` (thêm mã lỗi mới, ngày sai/kết thúc < bắt đầu/người giao không tồn tại cũng là 422).
- Hạn chỉ có ngày: tạo → `23:59`; sửa → giữ giờ cũ (cả Python lẫn Node).
- Lịch: tạo cần giờ bắt đầu (thiếu → model hỏi lại); kết thúc mặc định +1 giờ; lịch lặp không nói "tới khi nào" → lặp 1 năm (hợp đồng bắt buộc `endDate`), preview ghi "lặp … tới dd/MM/yyyy". Sửa lịch qua trợ lý không đổi kiểu lặp (YAGNI); dời giờ bắt đầu sự kiện một lần thì giờ kết thúc dời theo.
- Tool sửa/xoá nhận **id hoặc tên**; khớp đúng tên trước, ưu tiên việc chưa xong / lịch chưa qua; còn > 1 → `ask_user` ≤ 5 lựa chọn (trả lời bằng đúng nhãn lựa chọn thì chọn được).
- Thông báo tạo trong batch, push gửi **sau khi ghi** (`afterCommit`). Nhân tiện sửa lỗi có sẵn: tạo sự kiện chung trước đây chỉ gửi push, không lưu thông báo trong app.
- `previewContext` ở `server.ts` nay lọc việc/lịch/thu chi theo người hỏi (trước không lọc dù interface yêu cầu).

## Code review (8.5/10, không Critical/High) — đã xử lý
- M1 nhãn lựa chọn trùng (2 việc cùng tên + hạn) → hỏi lại vòng lặp: nhãn việc thêm người được giao; còn trùng thì thêm `#` + 4 ký tự cuối id.
- M2 mỗi lần Duyệt đọc DB tới 5 lần: kiểm guard + quyền chuyển VÀO `applyBatch` trên chính bản DB của batch (một lần đọc, không còn khe giữa kiểm và ghi); `ApplyDeps` bỏ `getShoppingItems/getTasks/getPlans/getUsers`.
- L1 tạo việc/lịch từ UI ghi lỗi vẫn gửi push → `writeRaw` trả boolean, ghi lỗi thì không push.
- L2 định nghĩa "lịch lặp" Python/Node lệch → cả hai chỉ xét `recurrenceType`.
- L4 (lỗi có sẵn) `POST /api/plans` sửa nhận nguyên body → đổi được `creatorId/createdAt`: `savePlan` bỏ các trường đó trước khi merge.
- L3 (sửa lịch có ngày cũ hỏng → 422) để nguyên: an toàn, chưa thấy dữ liệu như vậy.

## Success Criteria
Test xanh; ma trận quyền đúng như endpoint gốc; không ghi đè khi người khác vừa sửa.

## Security Considerations
Quyền kiểm theo người duyệt; agent không bỏ qua được optimistic lock.

## Next Steps
Phase 9.
