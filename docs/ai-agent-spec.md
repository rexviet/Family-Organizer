# Spec — Trợ lý AI Agent (Pydantic AI + CodeMode)

> Trạng thái: **Đã chốt hướng, chờ spike S1** · cập nhật 2026-10-10
> Thay thế: `/api/assistant/chat` hiện tại (một lần gọi Gemini, nhét 30 bản ghi vào prompt, không nhớ hội thoại).
> Pattern tham khảo: `everfit/foundry/workers/program-copilot-ptc` (CodeMode + Monty, agent chỉ *lập kế hoạch*, người dùng duyệt rồi mới ghi).

## 0. Quyết định đã chốt (2026-10-10)

| # | Câu hỏi | Chốt |
| :--- | :--- | :--- |
| D1 | Triển khai | **Sidecar: container riêng** `family-organizer-agent`, image riêng, cùng số phiên bản với app |
| D2 | Phạm vi v1 | **Đi chợ, Việc, Lịch, Thu chi — cả đọc và ghi** |
| D3 | LLM | **Bất kỳ endpoint tương thích OpenAI**; `base_url`, `api_key`, `model` đặt trong env của container agent. Không gắn với nhà cung cấp/model nào |
| D4 | Pha 0 | **Làm ngay** thành bản vá riêng: lọc quyền ở server + bỏ thu chi khỏi prompt assistant cũ cho con/khách |

---

## 1. Mục tiêu

| # | Mục tiêu | Đo bằng |
| :--- | :--- | :--- |
| G1 | Trả lời trên **toàn bộ** dữ liệu người hỏi được phép xem (bỏ giới hạn 30 bản ghi) | Eval §12: ≥ 85% câu đọc đúng |
| G2 | Hiểu hội thoại nhiều lượt ("thêm cái đó vào đi") | Eval nhóm câu nối |
| G3 | Tạo/sửa/xoá ở 4 module — **người dùng bấm Duyệt mới ghi** | 0 lần ghi không qua Duyệt |
| G4 | Không lộ dữ liệu vượt quyền | Test phân quyền §12 |

**Ngoài phạm vi v1:** tài sản/nợ/tiết kiệm/giấy tờ/sức khoẻ trẻ/ghi chú/thuốc (đọc ở v2), duyệt việc của trẻ (approve/reject điểm thưởng), agent tự chạy theo lịch.

## 2. Nguyên tắc (mượn từ PTC)

1. **Agent không bao giờ ghi.** Tool `propose_*` chỉ ghi thao tác vào `AppDeps.outcome`. Ghi thật do **Node** làm sau khi người dùng Duyệt (giống PTC: planner Python chỉ lập kế hoạch, workflow TS mới ghi).
2. **Preview do code dựng, không do LLM viết.** Card xác nhận được Node render từ `operations` có kiểu chặt.
3. **Dừng ngay khi đã có kết quả** (`EndWhenSettled`): có đề xuất hoặc cần hỏi lại → kết thúc lượt.
4. **Tool tự hỏi lại** khi mơ hồ ("mẹ" khớp 2 người, "việc đi chợ" khớp 3 việc) thay vì để model đoán.
5. **Quyền nằm ở server.** Tool đọc gọi API bằng token *của người hỏi*; lúc Duyệt, Node kiểm quyền *của người duyệt* bằng đúng luật của endpoint thường.
6. **Duyệt có khoá** (`planHash`) và **guard theo trạng thái hiện tại** (bản ghi bị người khác sửa sau khi đề xuất → không ghi đè).

## 3. Kiến trúc

```
Trình duyệt (Assistant.tsx)
   │ POST /api/assistant/agent {conversationId?, message}
   ▼
family-organizer (Node) ─ auth, rate-limit, flag, lưu hội thoại
   │ POST http://family-organizer-agent:3100/run   (X-Agent-Secret)
   ▼
family-organizer-agent (Python) ─ pydantic-ai Agent + CodeMode (Monty) ─► LLM tương thích OpenAI (env)
   │ tool đọc: GET http://family-organizer:3000/api/...  (Bearer token người hỏi)
   │ tool đề xuất: chỉ ghi vào AppDeps.outcome
   ▼ {answer | proposal | clarification}
Node lưu proposal + dựng preview → trình duyệt hiện card
   │ Duyệt: POST /api/assistant/proposals/:id/apply {planHash}
   ▼
Node: kiểm hash → kiểm quyền + guard từng operation → ghi qua FamilyDB → broadcastSyncEvent
```

### 3.1 Container agent

```yaml
  family-organizer-agent:
    image: ghcr.io/happysmartlight/family-organizer-agent:${FAMILY_ORGANIZER_VERSION:-latest}
    build: { context: ./agent }
    container_name: family_organizer_agent
    restart: unless-stopped
    # KHÔNG có `ports:` — chỉ app gọi được qua mạng nội bộ của compose.
    environment:
      - AGENT_LLM_BASE_URL=${AGENT_LLM_BASE_URL:-}    # vd https://api.openai.com/v1, http://ollama:11434/v1, …
      - AGENT_LLM_API_KEY=${AGENT_LLM_API_KEY:-}
      - AGENT_LLM_MODEL=${AGENT_LLM_MODEL:-}
      - AGENT_SHARED_SECRET=${AGENT_SHARED_SECRET:-}
      - APP_INTERNAL_URL=http://family-organizer:3000
      - TZ=Asia/Ho_Chi_Minh
    mem_limit: 384m
```

- Service app thêm `AGENT_URL=http://family-organizer-agent:3100` và `AGENT_SHARED_SECRET`.
- **Không mount `data/`, không docker socket.** Agent không có đường nào tới DB ngoài API.
- Không có agent (stack cũ chưa thêm service, hoặc env LLM trống) → app hiển thị "Trợ lý nâng cao chưa cấu hình" và dùng assistant cũ. `/api/health` của app **không** phụ thuộc agent.
- Agent có `GET /health` → `{ok, llmConfigured, model, version}`; app hiện ở Thiết lập → AI (không bao giờ hiện key).

### 3.2 Phát hành & cập nhật (hệ quả của D1)

- `release.yml` build **2 image** arm64 cùng tag: `family-organizer` và `family-organizer-agent`.
- `updater.sh`: thêm biến `AGENT_SERVICE` (mặc định `family-organizer-agent`). Khi cập nhật: nếu service này **có trong compose** (`dc config --services`) thì pull + `up -d` cả hai, chờ app healthy rồi chờ agent `/health`; rollback thì quay **cả hai** về bản cũ. Không có service → bỏ qua (tương thích stack cũ).
  - Vẫn đúng ràng buộc CLAUDE.md: app chỉ gửi tên hành động; danh sách service cố định trong updater; **không sửa compose**.
  - Agent lỗi sau cập nhật **không** kéo app rollback (agent là tính năng phụ) — chỉ ghi cảnh báo vào `state.env`.
- Thêm service vào compose của **liu-homelab** là việc **làm tay một lần** trên Pi; ghi hướng dẫn trong README + mục CHANGELOG của bản có agent.
- Cập nhật `docker-compose.yml` của repo (bản cài riêng) và `.env.example`.

> ⚠️ **Spike S1 (trước khi code agent):** (a) `pydantic-monty` có wheel linux/arm64 — chọn base `python:3.12-slim` (glibc) để tránh vấn đề musl; (b) RAM thực tế trên Pi 5; (c) 2–3 model tương thích OpenAI (vd một model lớn qua OpenRouter, một model nhỏ chạy Ollama) có viết được code Monty + gọi tool ổn không — 10 câu thử.

## 4. Hợp đồng Node ↔ Agent

**Node → Agent** `POST /run` (header `X-Agent-Secret`, so sánh constant-time):
```json
{
  "message": "Tháng này mẹ chi bao nhiêu?",
  "history": [ /* ModelMessage JSON các lượt trước, tối đa 20 lượt */ ],
  "user": { "id": "user_x", "fullName": "…", "role": "member" },
  "userToken": "<Bearer token của người hỏi>",
  "today": "2026-10-10", "weekday": "Thứ Bảy"
}
```
Key/URL/model LLM **không** đi qua Node — chỉ nằm trong env agent.

**Agent → Node** (một trong ba, kèm `history` mới + `usage`):
```json
{ "kind": "answer",        "reply": "…" }
{ "kind": "proposal",      "reply": "…", "operations": [ … ] }
{ "kind": "clarification", "question": "Bạn nói 'mẹ' là Lan hay bà ngoại?", "options": ["Lan", "Bà ngoại"] }
```

**Node → Trình duyệt** `POST /api/assistant/agent`:
```json
{ "conversationId": "…", "kind": "answer|proposal|clarification", "reply": "…",
  "options": [], "proposal": { "id": "…", "planHash": "…", "preview": [ /* dòng card do Node dựng */ ] } }
```

## 5. LLM tương thích OpenAI (D3)

```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

model = OpenAIChatModel(
    settings.llm_model,
    provider=OpenAIProvider(base_url=settings.llm_base_url, api_key=settings.llm_api_key),
)
```

- Yêu cầu tối thiểu với endpoint: **Chat Completions + tool calling** (CodeMode cần một tool `run_code`). Không cần JSON mode.
- Tuỳ chọn env: `AGENT_LLM_TEMPERATURE`, `AGENT_LLM_TIMEOUT_S` (mặc định 60), `AGENT_LLM_MAX_TOKENS`.
- Endpoint "tương thích" hay lệch chuẩn (PTC phải viết `cerebras_compat.py` vì Cerebras trả 400 với request OpenAI chấp nhận). Dự phòng: lớp `compat.py` nhỏ, bật theo `AGENT_LLM_COMPAT=…` — **chỉ thêm khi spike/eval thấy lỗi thật**.
- Thiếu một trong 3 biến → `/health` báo `llmConfigured=false`, `/run` trả 503.

## 6. Danh mục tool

Quy ước: tên tiếng Anh, **docstring tiếng Việt**, có kiểu trả về (TypedDict) để CodeMode sinh stub. Ngày `YYYY-MM-DD`, giờ `YYYY-MM-DD HH:mm`, tiền là **số nguyên VND**. Mỗi tool chỉ trả trường cần thiết (bỏ ảnh, `history`, `comments` dài).

### 6.1 Tool đọc (gọi API có sẵn)

| Tool | API |
| :--- | :--- |
| `list_members() -> list[Member]` (id, fullName, role, familyRelation) | `GET /api/users` |
| `list_tasks(status?, assignee_id?, due_from?, due_to?, query?) -> list[Task]` | `GET /api/tasks` |
| `list_plans(date_from, date_to, query?) -> list[PlanOccurrence]` — **bung lịch lặp** trong khoảng | `GET /api/plans` |
| `search_transactions(date_from, date_to, type?, category?, creator_id?, query?) -> list[Transaction]` | `GET /api/finance` |
| `list_expense_categories() -> list[Category]` | `GET /api/finance/categories` |
| `list_budgets(month) -> list[Budget]` | `GET /api/finance/budgets` |
| `list_recurring_bills() -> list[Bill]` | `GET /api/finance/recurring-bills` |
| `list_shopping(include_purchased=False) -> list[ShoppingItem]` | `GET /api/shopping` |
| `get_meal_plan() -> MealPlan \| None` | `GET /api/shopping/meal-plan/current` |

401/403 → tool ném lỗi tiếng Việt rõ ràng ("Tài khoản của bạn không xem được thu chi") để model trả lời đúng thay vì bịa.

### 6.2 Tool đề xuất (không ghi)

| Module | Tool | Operation `type` | Quyền (kiểm lại lúc apply, đúng luật endpoint gốc) |
| :--- | :--- | :--- | :--- |
| Đi chợ | `propose_add_shopping_items(items)` | `shopping.add` | mọi role đã đăng nhập (như `POST /api/shopping`) |
| | `propose_set_purchased(item_ids, purchased)` | `shopping.toggle` | như `POST /api/shopping/:id/toggle` |
| | `propose_remove_shopping_items(item_ids)` | `shopping.delete` | như `DELETE /api/shopping/:id` |
| Việc | `propose_create_task(title, due?, assignee_id?, priority?, reward_points?, is_shared?, description?)` | `task.create` | như `POST /api/tasks` |
| | `propose_update_task(task_id, changes)` — title/due/assignee/priority/status/description | `task.update` | con/khách chỉ việc mình tạo/được giao (`server.ts:911`) |
| | `propose_delete_task(task_id)` | `task.delete` | admin/member |
| Lịch | `propose_create_plan(title, start, end, is_shared?, recurrence?, description?)` | `plan.create` | admin/member/child |
| | `propose_update_plan(plan_id, changes)` | `plan.update` | người tạo hoặc admin |
| | `propose_delete_plan(plan_id)` | `plan.delete` | người tạo hoặc admin |
| Thu chi | `propose_create_transaction(type, amount, category, date, description, account?)` | `finance.create` | admin/member |
| | `propose_update_transaction(tx_id, changes)` | `finance.update` | admin/member |
| | `propose_delete_transaction(tx_id)` | `finance.delete` | admin/member |

- Mỗi tool **tự validate** (id tồn tại, thành viên đúng, ngày hợp lệ, `amount > 0`, category có thật, `end ≥ start`) và gọi `ask_user` nếu mơ hồ.
- Tool `update`/`delete` lưu kèm **`base`** của bản ghi lúc đề xuất: `updatedAt` (task/plan) hoặc `fingerprint` = sha256 các trường chính (transaction, shopping — vì `FinancialTransaction` không có `updatedAt`).
- Một lượt tối đa **10 operation**, một lần Duyệt.
- **Không** có tool sửa `rewardPoints` của việc đã hoàn thành, duyệt/trả việc của trẻ, hay đổi người tạo.

### 6.3 Tool hỏi lại

`ask_user(question: str, options: list[str] = [])` → ghi vào `AppDeps.clarifications`, kết thúc lượt.

## 7. Agent

```python
agent = Agent(
    model=model,                                    # §5
    deps_type=AppDeps,
    instructions=[base_instructions, date_anchor, member_glossary, category_glossary],
    toolsets=[read_toolset, propose_toolset, clarify_toolset],
    capabilities=[CodeMode(), EndWhenSettled()],
)
```

- `AppDeps` (tạo mới mỗi lượt): `http` (httpx, base `APP_INTERNAL_URL`, header token người hỏi), `user`, `today`, `outcome: OutcomeSlot`, `clarifications: ClarificationSink`.
- `EndWhenSettled`: như PTC — `after_node_run` trên `CallToolsNode`, trả `End` khi `outcome` có operation hoặc có câu hỏi.
- **Instructions:** vai trò + "trả lời ngắn, tiếng Việt"; "hôm nay là {today} ({weekday}), múi giờ Asia/Ho_Chi_Minh" (Monty không có `datetime.now()`); bảng thành viên + quan hệ (lấy sẵn ở đầu lượt); từ điển hạng mục chi; quy tắc "muốn thay đổi dữ liệu PHẢI dùng `propose_*`, không được nói là đã làm"; "xoá/sửa phải chỉ đúng bản ghi bằng id lấy từ tool đọc".
- Output validator (như `_refuse_an_unstaged_change` của PTC): câu trả lời kiểu "đã thêm/đã xoá/đã tạo…" mà không có operation → `ModelRetry`.
- Giới hạn: CodeMode `max_tool_calls=40`, `resource_limits` 15 s / 128 MiB mỗi snippet; một lượt ≤ 90 s; `UsageLimits(request_limit=6)`.

## 8. Pha 0 — lọc quyền ở server (D4, làm ngay)

**Vấn đề:**
1. `GET /api/tasks`, `GET /api/plans` trả **mọi** bản ghi cho mọi role; việc ẩn bản ghi riêng tư chỉ do UI làm (`Tasks.tsx:201`, `Schedules.tsx:229-236`). `GET /api/search` cũng vậy.
2. `/api/assistant/chat` đưa **giao dịch tài chính** vào prompt cho mọi role, kể cả con/khách (`server.ts:1935`), dù con/khách bị chặn ở `GET /api/finance`.

**Sửa:**
- `src/utils/visibility.ts`: `canSeeTask(task, viewer)`, `canSeePlan(plan, viewer)` — đúng luật UI đang dùng:
  - Việc: con/khách thấy việc chung + việc mình tạo/được giao; admin/member thấy hết (giữ nguyên hành vi UI hiện tại).
  - Lịch: admin thấy hết; còn lại thấy lịch chung + lịch mình tạo.
- Áp ở server cho `GET /api/tasks`, `GET /api/plans`, `GET /api/search`, prompt của `/api/assistant/chat`; UI dùng chung hàm (không đổi kết quả hiển thị).
- `/api/assistant/chat`: chỉ đưa giao dịch nếu người hỏi là admin/member.
- Kiểm tra thêm các nơi khác trả task/plan cho client (ICS feed, widget, bản tin tuần, đồng bộ realtime) và ghi lại nếu cùng lỗi.
  - Kết quả rà (2026-10-10): đồng bộ realtime chỉ gửi id; widget không trả task/plan. **ICS feed còn lỗi cùng loại**: một token chung cho cả nhà (`/api/calendar/feed-info` cấp cho mọi role), feed chứa **cả lịch riêng** của mọi người. Sửa cần token theo từng người → để bản sau, không nằm trong Pha 0.

## 9. Đề xuất & Duyệt (apply)

Lưu trong DB (collection mới, thêm theo kiểu không phá bản cũ — `normalizeDB` mặc định `[]`):

```ts
interface AgentProposal {
  id: string; conversationId: string; userId: string;
  operations: AgentOperation[];      // discriminated union theo `type`; trường lạ bị loại
  planHash: string;                  // sha256(JSON chuẩn hoá của operations)
  status: "pending" | "applied" | "partially_applied" | "cancelled" | "expired" | "failed";
  results?: { index: number; ok: boolean; id?: string; error?: string }[];
  createdAt: string; expiresAt: string;   // hết hạn sau 30 phút
  appliedAt?: string;
}
```

`POST /api/assistant/proposals/:id/apply {planHash}`:
1. Proposal của đúng người dùng, `pending`, chưa hết hạn, `planHash` khớp → nếu không: 409.
2. **Kiểm trước toàn bộ** (dry-run), không ghi gì nếu có lỗi:
   - Quyền của người duyệt theo đúng luật endpoint gốc — tách thành hàm dùng chung `server/permissions.ts` (`canEditTask`, `canDeletePlan`, `canWriteFinance`…) để endpoint thường và apply không lệch nhau.
   - Guard: bản ghi còn tồn tại, `updatedAt`/`fingerprint` khớp `base` (người khác vừa sửa → 409 "dữ liệu đã thay đổi, hỏi lại trợ lý"), thành viên/hạng mục còn tồn tại.
3. Ghi lần lượt qua các hàm `FamilyDB.save*/delete*` mà endpoint thường đang dùng (cùng validate, cùng ghi `history`, người thao tác = người duyệt), **đồng bộ trong một lượt event loop** (không `await` xen giữa) nên không request nào chen vào. Lỗi giữa chừng → dừng, `partially_applied` + `results` từng dòng.
4. `broadcastSyncEvent` cho từng module bị ảnh hưởng.
5. Idempotent: gọi lại khi đã `applied` → trả kết quả cũ, không ghi lần hai.

`POST /api/assistant/proposals/:id/cancel` → `cancelled`.

**Preview** (Node dựng từ operations, i18n có sẵn), mỗi operation một dòng; **xoá hiện màu đỏ**, sửa hiện `cũ → mới`:
`🛒 Thêm 5 món: sữa (2 hộp), trứng (10 quả)…` · `✅ Tạo việc "Đón con" — giao Bin — 17:00 11/10` · `✏️ Việc "Đổ rác": hạn 10/10 → 12/10` · `🗑️ Xoá khoản chi 250.000₫ · Ăn uống · 09/10`.

## 10. Hội thoại

```ts
interface AgentConversation {
  id: string; userId: string;
  messages: unknown[];      // pydantic-ai ModelMessage JSON
  createdAt: string; updatedAt: string;
}
```

- Mỗi người chỉ thấy hội thoại của mình. Gửi **20 lượt gần nhất** cho agent; nút "Cuộc trò chuyện mới".
- Xoá hội thoại không hoạt động > 30 ngày; proposal hết hạn dọn sau 7 ngày. Không đưa vào bản sao lưu Telegram.

## 11. Cấu hình & bật tắt

- `app_settings.agentEnabled` (admin bật ở Thiết lập → AI). Tắt hoặc agent chưa sẵn sàng → `/api/assistant/chat` cũ. Giữ endpoint cũ ≥ 1 bản phát hành sau khi agent ổn định.
- LLM chỉ cấu hình bằng env của container agent (D3). Màn hình Thiết lập chỉ **hiển thị** trạng thái + tên model.
- Rate limit: 20 lượt/giờ/người. Log mỗi lượt (không log nội dung ở production): user, số tool call, thời gian, token, kind, lỗi.

## 12. Kiểm thử

| Loại | Nội dung |
| :--- | :--- |
| Unit Node | `canSeeTask/canSeePlan` (Pha 0); `permissions.ts`; apply: hash sai, hết hạn, guard `updatedAt`/fingerprint lệch, thiếu quyền, idempotent, lỗi giữa chừng → `partially_applied` |
| Unit Python (pytest) | tool đọc (mock httpx), validate + `ask_user` của từng tool propose, `EndWhenSettled`, chuẩn hoá operation + `planHash` khớp với Node (test vector dùng chung) |
| Phân quyền (bắt buộc) | con/khách hỏi chi tiêu → bị từ chối; member không thấy việc/lịch riêng của member khác; con đề xuất `finance.create` → apply 403; con sửa việc của người khác → 403 |
| Hợp đồng | JSON schema cho `operations` dùng chung Node/Python (`agent/contracts/operations.schema.json`), test cả hai phía |
| Eval (LLM thật, **tách khỏi CI**) | ~50 câu tiếng Việt: đọc (tổng chi theo người/hạng mục/tháng, việc tuần này, lịch cuối tuần), ghi (đi chợ theo thực đơn, tạo việc có giao người, dời lịch, sửa/xoá khoản chi), câu nối, câu mơ hồ → phải hỏi lại. Chạy với từng model ứng viên |

## 13. Lộ trình

| Pha | Nội dung | Ra bản |
| :--- | :--- | :--- |
| **0** | §8 — lọc quyền server + vá assistant cũ | patch, **ngay** |
| **S1** | Spike §3.2 | — |
| **1** | Container agent + compose + release 2 image + updater; tool đọc 4 module; hội thoại; đi chợ (ghi); card Duyệt | minor |
| **2** | Ghi Việc + Lịch (create/update/delete) | minor |
| **3** | Ghi Thu chi; eval đầy đủ; cân nhắc gỡ `/api/assistant/chat` | minor |

Thu chi để sau cùng vì rủi ro sai số tiền cao nhất. Mỗi bản theo quy trình CLAUDE.md (CHANGELOG tiếng Việt → `npm run release`).

## 14. Rủi ro

| Rủi ro | Giảm thiểu |
| :--- | :--- |
| Model "tương thích OpenAI" yếu về tool calling / viết code | eval theo từng model; ghi model đã kiểm chứng trong README |
| Endpoint lệch chuẩn OpenAI | lớp `compat.py` khi có lỗi thật (§5) |
| Pi 5 thiếu RAM | `mem_limit`, đo ở S1 |
| Stack cũ chưa có service agent | app tự rơi về assistant cũ; updater bỏ qua service không tồn tại |
| Updater phức tạp hơn (2 service) | agent lỗi không rollback app; CI `sh -n`; thử cập nhật + quay về trên Pi trước khi phát hành |
| Lộ dữ liệu lên nhà cung cấp LLM | ghi rõ khi bật; tool chỉ trả trường cần thiết; cho phép dùng model chạy nội bộ (Ollama) |
| Prompt injection từ nội dung việc/lịch | agent không ghi được; mọi thay đổi qua card Duyệt do code dựng; xoá hiện đỏ |
| Xoá/sửa nhầm bản ghi | id bắt buộc lấy từ tool đọc; guard `base`; preview hiện `cũ → mới` |
