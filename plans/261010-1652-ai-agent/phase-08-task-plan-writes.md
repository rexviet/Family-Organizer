# Phase 8 — Ghi Việc + Lịch (M2)

**Priority:** P2 · **Effort:** 6h · **Status:** Pending

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
- [ ] permissions task/plan
- [ ] 6 tool đề xuất
- [ ] apply + preview 6 loại
- [ ] thử tay + phát hành 1.3.0

## Success Criteria
Test xanh; ma trận quyền đúng như endpoint gốc; không ghi đè khi người khác vừa sửa.

## Security Considerations
Quyền kiểm theo người duyệt; agent không bỏ qua được optimistic lock.

## Next Steps
Phase 9.
