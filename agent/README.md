# family-organizer-agent

Dịch vụ trợ lý AI (Python, Pydantic AI + CodeMode) chạy cạnh app Node. Spec: [docs/ai-agent-spec.md](../docs/ai-agent-spec.md).
Agent **chỉ đề xuất** — mọi thay đổi dữ liệu do Node ghi sau khi người dùng Duyệt.

> Trạng thái: phase 4 — agent thật với 9 tool đọc, `ask_user` và 3 tool đề xuất đi chợ. Tool đề xuất Việc/Lịch/Thu chi: phase 8–9.
> Triển khai (compose, biến `.env`, stack liu-homelab, cập nhật): [README gốc → Trợ lý nâng cao](../README.md#-trợ-lý-nâng-cao-ai-agent--tùy-chọn-từ-v120).

## Endpoint

Chỉ có hai endpoint, cổng `3100`, **không publish port** — chỉ app gọi được qua mạng compose.

| Endpoint | Mô tả |
| :--- | :--- |
| `GET /health` | `{ok, llmConfigured, model, version, contractVersion}` — không bao giờ có key/base_url |
| `POST /run` | Header `X-Agent-Secret` (so sánh constant-time). Body theo spec §4 |

Mã lỗi của `/run` (body luôn là `{"error": "<mã>"}`):

| HTTP | `error` | Khi nào |
| :--- | :--- | :--- |
| 400 | `client_disconnected` | Node ngắt khi đang gửi body |
| 401 | `unauthorized` | Sai/thiếu `X-Agent-Secret` (kiểm **trước** mọi thứ khác) |
| 503 | `llm_not_configured` | Thiếu 1 trong 3 biến `AGENT_LLM_BASE_URL/API_KEY/MODEL` |
| 413 | `too_large` | Body > `AGENT_MAX_BODY_BYTES` |
| 422 | `invalid_request` | Body sai — kèm `errors[{loc,msg,type}]`, **không** echo giá trị (tránh lộ token) |
| 429 | `busy` | Đã đủ số lượt đồng thời — trả ngay, không xếp hàng |
| 504 | `timeout` | Lượt chạy quá `AGENT_RUN_TIMEOUT_S` |
| 502 | `llm_error` | Endpoint LLM lỗi (chi tiết chỉ log tên lớp lỗi) |

Thành công: `{kind, reply, history, usage:{requests,toolCalls,inputTokens,outputTokens}, contractVersion}` — `kind` là một trong:

| `kind` | Trường thêm | Ghi chú |
| :--- | :--- | :--- |
| `answer` | — | `reply` là câu trả lời của model |
| `proposal` | `operations` | Đã qua validator hợp đồng (không bao giờ trả đề xuất sai). `reply` do **code** dựng ("Mình đề xuất N thay đổi…"), không phải model |
| `clarification` | `question`, `options` | Đúng chữ do tool `ask_user`/tool đề xuất ghi; `reply` = `question`. Có cả câu hỏi lẫn đề xuất thì câu hỏi thắng |

`history` là `ModelMessagesTypeAdapter` JSON, đã cắt còn 20 lượt gần nhất (chỉ cắt ở tin nhắn người dùng, không để tool call mồ côi),
bỏ `instructions` (dựng lại mỗi lượt). Với `proposal`/`clarification` lượt kết thúc bằng lời dẫn của code nên lượt sau có ngữ cảnh.
Vượt `request_limit` (6 request model/lượt) → `answer` "câu hỏi phức tạp, hãy hỏi gọn hơn" (không phải 502).
Node phải từ chối khi `contractVersion` lệch với bản của mình.

## Biến môi trường

| Biến | Mặc định | Ghi chú |
| :--- | :--- | :--- |
| `AGENT_SHARED_SECRET` | — | **Bắt buộc**, ≥ 32 ký tự ASCII in được (vd `openssl rand -hex 32`); sai → container thoát (exit 2, không in giá trị) |
| `AGENT_LLM_BASE_URL` | — | Endpoint tương thích OpenAI (Chat Completions + tool calling), vd `https://api.openai.com/v1` |
| `AGENT_LLM_API_KEY` | — | |
| `AGENT_LLM_MODEL` | — | Đổi model không cần build lại |
| `AGENT_LLM_TEMPERATURE` | (không gửi) | 0–2 |
| `AGENT_LLM_TIMEOUT_S` | `60` | Timeout mỗi request tới LLM |
| `AGENT_LLM_MAX_TOKENS` | (không gửi) | |
| `APP_INTERNAL_URL` | `http://family-organizer:3000` | App Node trong mạng compose — tool đọc gọi 9 endpoint GET (allowlist cứng, timeout 10 s) bằng `agentToken` của lượt |
| `AGENT_VERSION` | `dev` | CI truyền qua `--build-arg AGENT_VERSION=X.Y.Z` |
| `AGENT_RUN_TIMEOUT_S` | `90` | Timeout cứng của một lượt |
| `AGENT_CODE_MAX_DURATION_S` | `15` | Tổng thời gian chạy code của model (Monty) trong một lượt; 2× giá trị này phải < `AGENT_RUN_TIMEOUT_S`. Xem "Lưu ý vận hành" |
| `AGENT_MAX_CONCURRENT_RUNS` | `2` | Quá thì 429 |
| `AGENT_MAX_BODY_BYTES` | `4194304` | |

Biến để rỗng (`${X:-}` trong compose) được coi như không đặt. Chỉ đọc đúng các tên trên (có tiền tố) — biến
kiểu `LLM_API_KEY` của service khác trong stack không ảnh hưởng.

## Model đã kiểm chứng (spike phase 1, [báo cáo](../plans/261010-1652-ai-agent/reports/spike-s1.md))

| Model | Điểm 10 câu | Ghi chú |
| :--- | :--- | :--- |
| `kr/deepseek-3.2` | 10/10 | Khuyến nghị thời spike (nay xem bảng eval phase 9 bên dưới); chậm hơn (đến ~24 s câu đọc nhiều bước) |
| `kr/qwen3-coder-next` | 8/10 | |
| `kr/claude-haiku-4.5` | 7–9/10 | Nhanh nhất (≤ 11 s) |
| `kr/claude-sonnet-4.5` | 7/10 | |

Các model trên chạy qua router OpenAI-compatible của người dùng; nguồn này có thể đổi bất ngờ → app luôn có
đường lui về assistant cũ. Không model nào cần sửa request (chưa cần lớp `compat.py`).

Phase 4 (10 câu, [báo cáo](../plans/261010-1652-ai-agent/reports/phase-04-real-model.md)): `kr/deepseek-3.2` 9–10/10 qua
5 lần, `kr/claude-haiku-4.5` 10/10. Eval đầy đủ phase 9 (57 câu, cả ghi Thu chi;
[báo cáo](../plans/261010-1652-ai-agent/reports/phase-09-eval.md)):

| Model | Eval 57 câu (strict) | Sai số tiền | Ghi chú |
| :--- | :--- | --: | :--- |
| `anthropic/claude-haiku-5.5` (OpenRouter) | **Đợt 3, code cuối: 100% / 100%** | 0 | **Khuyến nghị**; nhanh nhất (≤ 9 s/câu); smoke phase 8 10/10 |
| `deepseek/deepseek-v4-pro` (OpenRouter) | Đợt 3, code cuối: 98% / 98% | 0 | Đạt ngưỡng; chậm hơn (≤ 51 s/câu); smoke phase 8 9/10 |
| `deepseek/deepseek-v4-flash` (OpenRouter) | Đợt 3, code cuối: 98% / 95% | 0 | Đạt ngưỡng, **rẻ nhất**; đôi khi hỏi lại thừa; smoke phase 8 8/10 |
| `qwen/qwen3-coder-next` (OpenRouter) | – (chỉ smoke phase 8: 7/10) | – | Chưa chạy eval 57 câu |
| `google/gemini-2.5-flash-lite` (OpenRouter) | – (chỉ smoke phase 8: 3/10) | – | **Không dùng được** — hay trả lời 0 tool call |
| `kr/deepseek-3.2` (router local) | Đợt 1: 77% / 84%. Đợt 2 (sau sửa, code chưa cuối): 72% — code cuối mới đo 15 câu khó: 12/15 | 0 | Chậm (≤ 55 s/câu, có câu > 100 s) |
| `kr/claude-haiku-4.5` (router local) | Đợt 1: 75% / 74%. Đợt 2 (sau sửa, code chưa cuối): 84% | 0 | Nhanh (≤ 10 s/câu); hay hỏi lại bằng chữ thay vì `ask_user` |

Mọi lần: 0 request ghi tới app, câu vượt quyền 5/5. Ngưỡng ≥ 85% strict **đạt** với code cuối (đợt 3, 2026-10-11,
OpenRouter: `AGENT_LLM_BASE_URL=https://openrouter.ai/api/v1`). Router `kr/*` hết hạn mức tháng nên chưa đo lại code cuối.

## Eval

`eval/run_eval.py` + `eval/cases.json` (57 câu: đọc, ghi Đi chợ/Việc/Lịch/Thu chi, câu nối, mơ hồ, vượt quyền khi đăng nhập
Con) + app giả `eval/fixtures/app.json`. Không nằm trong image, không chạy bởi pytest (luật chấm có unit test ở
`tests/unit/test_eval_harness.py`). Điểm dao động giữa các lần → chạy mỗi model ≥ 2 lần:

```sh
cd agent
AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=x \
  uv run python eval/run_eval.py --models kr/deepseek-3.2 kr/claude-haiku-4.5 --runs 2
```

Chạy tuần tự (hai tiến trình song song làm router trả 429). Báo cáo ghi vào
`plans/261010-1652-ai-agent/reports/eval-<model>-<ngày>.md` (ghi đè báo cáo cùng ngày). Tiêu chí: ≥ 85% với model khuyến nghị,
**0 operation thu chi sai số tiền**, 0 request ghi tới app (lệnh trả mã 1 nếu vi phạm hai điều sau).

## Chạy local

```sh
cd agent
uv sync                                   # Python 3.12, cài cả nhóm dev
uv run pytest                             # unit + vector hợp đồng (agent/contracts/vectors.json)
uv run ruff check src tests && uv run mypy

AGENT_SHARED_SECRET=$(openssl rand -hex 32) \
AGENT_LLM_BASE_URL=http://localhost:20128/v1 AGENT_LLM_API_KEY=... AGENT_LLM_MODEL=kr/deepseek-3.2 \
uv run python -m family_agent             # nghe 0.0.0.0:3100
```

Image arm64 (Pi):

```sh
docker build --platform linux/arm64 --build-arg AGENT_VERSION=dev -t family-organizer-agent agent
docker run --rm -p 127.0.0.1:3100:3100 -e AGENT_SHARED_SECRET=... family-organizer-agent   # thử local
curl localhost:3100/health
```

Image chạy user `app` (uid 10001), không mount gì, có `HEALTHCHECK` gọi `/health`. Schema hợp đồng được chép vào
`/app/contracts` (`AGENT_CONTRACTS_DIR`).

## Phụ thuộc

Pin **chính xác** theo spike: `pydantic-ai-slim[openai]==2.33.0`, `pydantic-ai-harness[codemode]==0.25.0`,
`pydantic-monty==0.0.21` (monty 1.x đổi tên key `resource_limits` → mọi `run_code` lỗi). Luôn commit `uv.lock`;
image build bằng `uv sync --frozen`.

## Log

Mỗi lượt một dòng JSON: `userId, role, status, kind, requests, toolCalls, inputTokens, outputTokens, ms` (lỗi: `error` =
tên lớp). **Không** log nội dung hội thoại, token, key hay URL LLM.

## Hợp đồng operation

`src/family_agent/contract.py` — `canonical`, `plan_hash`, `fingerprint`, `validate_operations`; xem
[contracts/README.md](contracts/README.md). Đổi hợp đồng → tăng `contractVersion`, sửa cả bản Node
(`server/agentContract.ts`) và `vectors.json` trong cùng một thay đổi.

## Cấu trúc `harness/` (phase 4)

| File | Vai trò |
| :--- | :--- |
| `agent.py` | `run_turn`: dựng deps + agent, chạy, đổi kết quả thành 3 kind + history; output validator ("đã thêm…" mà không có đề xuất → `ModelRetry`) |
| `deps.py` | `AppDeps` mỗi lượt; client HTTP chỉ-GET + allowlist 9 endpoint; cache 1 request/endpoint/lượt; lỗi tiếng Việt cố định (không URL/token) |
| `outcome.py`, `clarify.py` | `OutcomeSlot` (≤ 10 op, không trùng, mỗi op qua `contract.validate_operations`), `ClarificationSink` |
| `end_when_settled.py` | Kết thúc lượt ngay khi có đề xuất hoặc câu hỏi (không request model thứ 2) |
| `prompts.py` | Instructions: ngày/thứ, tuần này (Thứ Hai–Chủ nhật), bảng thành viên, hạng mục chi, luật đề xuất, 6 ví dụ |
| `money.py` | `parse_vnd`: "250k", "1tr2", "1,5 triệu", "2 triệu rưỡi"… → số nguyên đồng; nhập nhằng ("1,5", "1.500k") → lỗi để model hỏi lại |
| `recurrence.py` | Bản port `src/utils/recurrence.ts`; case kiểm dùng chung `src/utils/recurrence.cases.json` (vitest + pytest) |
| `tools/read.py`, `tools/shopping.py`, `tools/ask.py` | 9 tool đọc, 3 tool đề xuất đi chợ, `ask_user` |
| `tools/tasks.py`, `tools/plans.py`, `tools/finance.py` (+ `tools/records.py` dùng chung) | 3 tool đề xuất mỗi module Việc/Lịch/Thu chi; tìm bản ghi theo id hoặc tên, mơ hồ → hỏi lại ≤ 5 lựa chọn |

`agentToken` chỉ nằm trong header của client HTTP của lượt — không vào instructions, tham số/kết quả tool, history hay log.

## Lưu ý vận hành

- **Monty chạy đồng bộ trên event loop** (đo ở phase 4): code vô hạn của model làm `/health` và mọi lượt khác treo. `harness/code_guard.py`
  chặn: một `run_code` mỗi phản hồi, không `restart`, và tổng thời gian chạy code của lượt ≤ `AGENT_CODE_MAX_DURATION_S` (mặc định 15 s;
  hết thì từ chối `run_code` tiếp). Treo liên tục tối đa ≈ một ngân sách, cả lượt ≲ hai ngân sách nên cấu hình bắt buộc
  `2 × AGENT_CODE_MAX_DURATION_S < AGENT_RUN_TIMEOUT_S` (mặc định 30 < 90). Lượt vẫn bị cắt
  cứng ở `AGENT_RUN_TIMEOUT_S` ở điểm `await` kế tiếp (504).
- `APP_INTERNAL_URL` phải là URL gốc (không path). Model không làm nổi yêu cầu (hết retry) → `answer` thân thiện, không phải 502.
- Thử tay với model thật: `eval/phase4_smoke.py`, `eval/phase8_smoke.py` (10 câu) và eval đầy đủ `eval/run_eval.py` (mục "Eval")
  — không nằm trong image, không chạy bởi pytest.
