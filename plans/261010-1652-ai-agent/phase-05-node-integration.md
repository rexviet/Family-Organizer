# Phase 5 — Node: proxy, lưu trữ, Duyệt/apply

**Priority:** P1 · **Effort:** 16h · **Status:** Done (2026-10-10)

## Context Links
- Spec §3, §4, §8, §9, §10, §11
- `server.ts`: `requireAuth`/`requireRole` (~dòng 273), endpoint đi chợ `POST /api/shopping` (~2200), `toggle`, `DELETE /api/shopping/:id`; assistant cũ `/api/assistant/chat`; `aiStatus()` (~94); `broadcastSyncEvent`
- `server/sqlite.ts` (mẫu bảng riêng `server_metrics` dòng 143), `server/db.ts` (`FamilyDB.save*/delete*`)
- Pha 0: `src/utils/visibility.ts`

## Overview
Node là nơi duy nhất ghi dữ liệu. Phase này: lưu hội thoại/đề xuất, gọi agent, dựng preview, apply operation **đi chợ** (khung apply dùng cho cả 12 loại; loại chưa bật trả 501).

## Key Insights
- **Lưu riêng `data/agent.db`** (better-sqlite3, file riêng) — không vào `FamilyOrganizerDB` vì `sqliteSave` ghi lại toàn bộ DB mỗi lần. Tự nằm ngoài backup/snapshot; bản cũ bỏ qua file này → "Quay về" an toàn.
- Quyền khi apply phải **đúng luật endpoint gốc** → tách luật ra `server/permissions.ts`, endpoint gốc gọi lại chính hàm đó (refactor không đổi hành vi, có test trước).
- `FamilyDB.save*` đồng bộ → chạy hết operation trong một lượt event loop, không `await` xen giữa.

## Requirements
**Lưu trữ** — `server/agentStore.ts`:
```sql
agent_conversations(id TEXT PK, user_id TEXT, messages TEXT, created_at TEXT, updated_at TEXT)
agent_proposals(id TEXT PK, conversation_id TEXT, user_id TEXT, operations TEXT, plan_hash TEXT,
                status TEXT, results TEXT, created_at TEXT, expires_at TEXT, applied_at TEXT)
```
Dọn: hội thoại không hoạt động > 30 ngày, proposal > 7 ngày — gắn vào timer dọn dẹp sẵn có.

**API**
- `POST /api/assistant/agent {conversationId?, message}` (requireAuth):
  1. flag `agentEnabled` + agent `/health` ok (cache 30 s) + `contractVersion` khớp — nếu không: **503** `{fallback:true}` để UI dùng `/api/assistant/chat`.
  2. Rate limit 20 lượt/giờ/người (bộ đếm trong bộ nhớ).
  3. **Cấp token agent** cho lượt này rồi gọi `AGENT_URL/run` (timeout 100 s) với history. **Không** gửi token đăng nhập của người dùng (token hiện không hết hạn, không thu hồi được, `server.ts:143-158`).
  4. `proposal` → `validateOperations` (phase 2) → lưu proposal (`expires_at = +30 phút`) → `buildPreview(ops)`.
  5. Lưu history; trả spec §4.
- `GET /api/assistant/conversations/latest`, `POST /api/assistant/conversations` (mới) — chỉ của chính mình.
- `POST /api/assistant/proposals/:id/apply {planHash}` và `/cancel` — spec §9.
- `GET /api/settings/agent` (admin): `{enabled, reachable, llmConfigured, model, version}`; `POST` bật/tắt `agentEnabled`.

**Apply engine** — `server/agentApply.ts`: `apply(proposal, session) → results[]`
1. kiểm chủ sở hữu/trạng thái/hạn/hash → 409.
2. dry-run toàn bộ: `permissions.can*(op, session)` + guard (`base.updatedAt`/`fingerprint` so với bản ghi hiện tại; id tồn tại).
3. ghi toàn bộ trong **một** `FamilyDB.applyBatch` (người thao tác = người duyệt) — xem "Điều chỉnh sau red-team"; lỗi → không ghi gì, `failed` + lý do.
4. `broadcastSyncEvent` theo module; idempotent khi đã `applied`.
- Bật ở M1: `shopping.add`, `shopping.set_purchased`, `shopping.delete`. Loại khác → 501 "chưa hỗ trợ".

**Preview** — `server/agentPreview.ts`: mỗi op → `{icon, text, tone: "add"|"edit"|"delete"}`, tiếng Việt, tiền `vi-VN`, ngày `dd/MM HH:mm`; sửa hiện `cũ → mới`.

## Related Code Files
- Tạo: `server/agentStore.ts`, `server/agentClient.ts` (gọi agent, timeout, secret), `server/agentApply.ts`, `server/agentPreview.ts`, `server/permissions.ts` + `*.test.ts` tương ứng
- Sửa: `server.ts` (route mới; endpoint đi chợ gọi `permissions.ts`), `server/db.ts` nếu cần hàm `getShoppingItem(id)`

## Implementation Steps (TDD)
1. Bản vá riêng trước: `POST /api/tasks` bỏ điều kiện `&& !req.body.comments` (`server.ts:915` — con/khách gửi kèm `comments` là sửa được việc của người khác; bình luận đã có endpoint riêng `:941`). Sau đó mới khoá hành vi bằng test và tách `permissions.ts` cho việc/lịch/thu chi (đi chợ **không** cần: mọi role sửa/xoá mọi món, không có luật riêng).
2. `agentStore.ts` + test (DB tạm trong thư mục tmp).
3. `agentPreview.ts` + test snapshot từng loại op.
4. `agentApply.ts` + test: hash sai, hết hạn, người khác bấm, guard lệch, thiếu quyền (con xoá món người khác nếu luật gốc cấm), idempotent, ghi lỗi → không còn dòng nào trong DB.
5. `agentClient.ts` + test với server giả (`http.createServer`).
6. Route + test tích hợp (supertest-style bằng `fetch` tới app khởi động trên cổng tạm, hoặc tách hàm handler để test).
7. Rate limit + flag + fallback.

## Todo
- [x] permissions.ts — bản vá `comments` + `sanitizeTaskWrite` đã có từ commit `c4443b1`; đi chợ không có luật riêng (mọi vai trò đã đăng nhập), luật việc/lịch/thu chi tách tiếp ở phase 8–9 khi bật ghi
- [x] agent.db store + dọn dẹp (`server/agentStore.ts`, gắn vào timer 30 phút; `applying` → `failed` lúc khởi động)
- [x] preview (`server/agentPreview.ts`, đủ 12 loại op, tên bản ghi lấy từ DB)
- [x] apply engine + guard (`server/agentApply.ts`, đồng bộ, một `FamilyDB.applyBatch`)
- [x] agent client (`server/agentClient.ts`, health cache 30 s, run timeout 100 s)
- [x] token agent 120 s chỉ-GET allowlist (`server/agentToken.ts`, nối vào `authMiddleware`, thu hồi khi lượt xong)
- [x] ID hậu tố ngẫu nhiên (shop/task/plan/tx/log) + `applyBatch`/`writeRawOrThrow` + hàm thuần `server/dataMutations.ts`
- [x] routes + rate limit + flag + fallback (`server/agentRoutes.ts`)
- [x] settings/agent
- [x] M5: đổi vai trò / xoá người dùng → xoá hội thoại + proposal pending

## Kết quả (2026-10-10)

- `npm run lint && npm test` xanh. Test mới: `db.batch`, `agentToken`, `agentStore`, `agentPreview`, `agentApply`, `agentClient`, `agentRoutes`.
- Chạy thật (app trong thư mục tạm + agent Python phase 4 + model `kr/deepseek-3.2`): "thêm 1kg cà chua và hành lá vào đi chợ"
  → card `🛒 Thêm 2 món: Cà chua (1kg), Hành lá` → Duyệt → 2 món trong DB; SSE phát `SHOPPING_UPDATE`. Token agent: GET `/api/shopping` 200,
  POST `/api/shopping` 401, GET `/api/users/:id` 401.

### Quyết định khi làm (--auto)
- Token agent: `agt.<base64url(userId)>.<exp>.<nonce>.<hmac>` (base64url để id có dấu chấm không phá định dạng); khoá HMAC dẫn xuất từ
  `SESSION_SECRET` (khác HMAC token đăng nhập); nonce giữ trong bộ nhớ → thu hồi ngay khi lượt xong (restart app = mọi token agent hết hiệu lực).
- Proposal của người khác → **404** (không lộ tồn tại), không phải 409. Guard lệch / op chưa hỗ trợ → proposal chuyển `failed` (không thể thành công nữa).
- `agent.db` thêm cột `turns` (dòng hiển thị cho UI — history ModelMessage không dùng để vẽ chat được), `preview`, `error`. `GET …/latest` không gửi
  history thô xuống trình duyệt; trả `available` để UI phase 6 biết dùng agent hay assistant cũ.
- Một người chỉ một lượt cùng lúc (429) — tránh hai lượt ghi đè history của nhau. Rate limit chỉ đếm lượt thực sự gọi agent.
- Lỗi khi chạy (`llm_error`, `timeout`, không kết nối, phản hồi sai/lệch `contractVersion`) → 503 `{fallback:true}`; agent `busy` → 429 (không fallback).
- Đề xuất sai hợp đồng → không lưu, trả `answer` xin nói lại.
- Hàm thuần mới chỉ cho đi chợ (`mutateAddShopping/SetShoppingPurchased/DeleteShopping`); `mutateSaveTask/Plan/Transaction` để phase 8–9 (YAGNI ở M1).
  ID mới có hậu tố đã áp cho task/plan/tx ngay. Bản cũ đọc ID dạng mới bình thường (chỉ là chuỗi) → "Quay về" an toàn.
- `categoryLabel` cho preview thu chi chưa nối (M1 không có op thu chi) — phase 9.

### Code review (8/10, 0 Critical/High) — đã sửa
- M1 lộ dữ liệu qua preview: chỉ lưu/dựng preview cho loại op đã bật (loại khác → `answer`); `previewContext` lọc theo
  `canSeeTask/canSeePlan/canSeeFinance` của người hỏi, đọc DB một lần (`FamilyDB.readSnapshot`).
- M2 ghi family.db xong mà agent.db lỗi → vẫn trả thành công + broadcast.
- M3 hội thoại bị xoá (đổi vai trò) trong lúc agent chạy → 409, không tạo proposal.
- L2 agent.db hỏng không làm sập app (DB tạm trong bộ nhớ + tắt agent); L3 hậu tố ID 12 hex; L5 tắt agent → không Duyệt được; L6 "mới" dùng lại hội thoại trống.
- Để lại: L1 (guard lệch vì món đã ở trạng thái đích/đã bị xoá vẫn tính conflict — giữ đúng luật "guard bằng `updatedAt`"), L7 (`/api/realtime` không
  xác thực — lỗi có sẵn, ngoài phạm vi).

## Success Criteria
`npm run lint && npm test` xanh; chạy với agent thật (phase 4): "thêm sữa, trứng vào đi chợ" → card → Duyệt → món xuất hiện ở tab Đi chợ của máy khác (sync realtime).

## Security Considerations
- Token người dùng chỉ chuyển cho agent trong mạng nội bộ compose; agent không lưu.
- Mọi operation được validate schema **trước khi lưu** và kiểm quyền **lúc apply** theo người duyệt, không theo người đề xuất.
- Không ai apply được proposal của người khác (kể cả admin).

## Next Steps
Phase 6.

## Điều chỉnh sau red-team (bắt buộc)

**Token agent ngắn hạn, chỉ đọc (C2).** `server/agentToken.ts`: `agt.<userId>.<exp>.<nonce>.<hmac>` (HMAC bằng `SESSION_SECRET`, sống 120 s). `authMiddleware` nhận token `agt.` **chỉ** cho `GET` trên allowlist 9 endpoint đọc của phase 4; mọi thứ khác 401. Test: token agent bị 401/403 ở `POST /api/shopping`, `GET /api/users/:id`, backup, update, settings.

**ID không trùng + ghi lỗi không bị nuốt (C1, M9).** `db.ts`: ID mới ở `addShoppingItem`/`saveTask`/`savePlan`/`saveTransaction` thêm hậu tố ngẫu nhiên (`${prefix}_${Date.now()}_${rand}`, giống `log_`/`reward_`). Thêm `FamilyDB.applyBatch(fn)`: đọc 1 lần, `fn` sửa trên bản đọc, `writeRaw` 1 lần và **ném lỗi** nếu ghi thất bại (biến thể `writeRawOrThrow`; `writeRaw` cũ giữ nguyên hành vi). `save*` hiện tự `readRaw`/`writeRaw` nên phải **tách phần sửa dữ liệu thành hàm thuần** `mutateAddShopping(db, …)`, `mutateSaveTask(db, …)`… (giữ nguyên validate, `history`, `logActivity` vào `db.activityLogs`); `save*` cũ gọi lại các hàm này nên hành vi endpoint không đổi (có test khoá trước khi tách). Apply dùng `applyBatch` → cả proposal là **một** transaction SQLite: hoặc ghi hết, hoặc không ghi gì (bỏ trạng thái `partially_applied`). Test: 1 proposal 30 món → đúng 30 dòng trong DB.

**Apply idempotent qua 2 DB (H4).** Trước khi ghi: `UPDATE agent_proposals SET status='applying' WHERE id=? AND status='pending'` và kiểm `changes===1`; ghi `family.db`; rồi `applied`. Khởi động app: proposal còn `applying` → `failed` (không chạy lại), card báo "kiểm tra lại dữ liệu". Kiểm hash/trạng thái/quyền + ghi nằm trong một khối đồng bộ, không `await`.

**Đi chợ (M1).** `set_purchased`: bằng trạng thái hiện tại → bỏ qua (không lật); khác → đặt giá trị. Guard bằng `updatedAt`.

**Reply không mâu thuẫn card (L4).** Câu trả lời của model hiển thị tách khỏi card; nhãn dòng sửa/xoá lấy từ DB (tên thật của bản ghi), không lấy từ chữ agent.

**Đổi quyền (M5).** Khi role của người dùng đổi hoặc người dùng bị xoá → xoá hội thoại + proposal `pending` của họ trong `agent.db`.
