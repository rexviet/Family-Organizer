# Spike S1 report (phase 1) — CHỐT: GO (2026-10-10)

> Kết luận cuối ở mục **"Chốt phase 1"** cuối file. Các phần tiếng Anh bên dưới là ghi chép lúc làm spike.

Date 2026-10-10. Scope done: reqs 1, 3, 2 (Mac only), harness for 4. NOT done: Pi RAM, live model runs.
Files: `agent/spike/` (untracked; pyproject, uv.lock, Dockerfile, checks.py, ram.py, eval_quality.py).

## Environment
- macOS (Darwin 25.4, Apple Silicon), Docker buildx native `linux/arm64`, base `python:3.12-slim` (CPython 3.12.15, glibc), uv from `ghcr.io/astral-sh/uv`.
- Container verified `uname -m` = aarch64. Image 415 MB (spike with full deps, uncompressed).
- Ollama (localhost:11434) NOT reachable; LM Studio (1234) not reachable; `AGENT_LLM_*` env not set -> no live LLM run.

## Versions to pin (resolved + tested in the arm64 container)
```
pydantic-ai-slim[openai]==2.33.0     # not the full `pydantic-ai` (see findings)
pydantic-ai-harness[codemode]==0.25.0
pydantic-monty==0.0.21               # MUST pin, see finding 1
pydantic-graph 2.33.0, pydantic 2.14.0, openai 3.28.0, httpx 0.28.1, anyio 4.15.1
```
Same trio as the PTC lockfile (slim 2.33.0 / harness 0.25.0 / monty 0.0.21). 38 packages total with slim.

## Results
| Req | Result | Evidence |
| :-- | :-- | :-- |
| 1 Monty on linux/arm64 | PASS | `docker buildx build --platform linux/arm64` ok; wheels install (pydantic-monty 0.0.21 prebuilt, no Rust build). `checks.py::check_basic` in container (aarch64): `tools shown to model: ['run_code']`, `run_code return: {'p': 72, 't': 72}` (asyncio.gather over 2 tool calls) |
| 3a `capabilities=[CodeMode(), EndWhenSettled]` + `after_node_run` | PASS | Custom `AbstractCapability.after_node_run` returning `End(FinalResult(None))` when `ctx.deps.outcome` set: FunctionModel saw exactly **1 request**, outcome recorded, `result.output is None`. Same code as PTC `_EndWhenSettled`. `UsageLimits(request_limit=6)` accepted |
| 3b Monty `resource_limits` on arm64 | PASS | Infinite loop, `max_duration_secs=1.0`: stops at 1.01 s, `TimeoutError: time limit exceeded`. `[0]*200_000_000` with `max_memory=32MiB`: 0.02 s, `MemoryError: memory limit exceeded`. Both surface to the model as a retryable tool error (not an exception to the host). Bad key -> `UserError: Unknown resource_limits key(s)` |
| 3c history round-trip | PASS | `ModelMessagesTypeAdapter.dump_json(r.all_messages())` -> `validate_json` -> `message_history=` in 2nd run (2nd run saw 3 msgs). Also with `run_code` tool-call/return parts in history (957 B JSON for a 1-tool run) |
| 3d Ollama tool calling with CodeMode | NOT TESTED | no Ollama; needs access |
| 2 RAM (Mac arm64, NOT Pi) | PASS on Mac | see below |
| 4 Model quality | NOT RUN | harness ready, plumbing verified with scripted model (`--selftest`), checker discriminates (4/10 for a canned reply) |

### RAM (Mac arm64 Docker VM, NOT Pi)
Process = python + pydantic-ai + openai provider + CodeMode, no FastAPI/uvicorn yet. Run = 1 `run_code` with 5 parallel tool calls (200-item payloads).
- In-container `/proc/self/status`: RSS after import 84 MiB; idle 84; after 1st run 86; after 20 runs 86 MiB (no growth). **VmHWM (peak) 123 MiB** (set during import).
- `docker stats --no-stream` : idle 73.9 MiB; during runs 75-84 MiB.
- Estimate with FastAPI+uvicorn: +20-30 MiB -> ~150 MiB peak, under the 300 MiB threshold with margin. Latency of the scripted run: 0.25 s/run (tool sleeps 0.2 s), i.e. Monty overhead is small. Pi 5 numbers: TODO.

## Library API findings (differ from spec/plan)
1. **`pydantic-monty` must be pinned `==0.0.21`.** Harness 0.25.0 declares `pydantic-monty>=0.0.19` with no ceiling; a fresh resolve picks 1.1.0 (released 2026-10-05), whose `ResourceLimits` keys were renamed (`max_feed_duration_secs`, `max_turn_duration_secs`, ...) -> every `run_code` fails with `ValueError: unknown limits key 'max_duration_secs'; accepted keys are 'max_feed_duration...'`. Plan/phase 3 pyproject should pin monty exactly (and commit `uv.lock`).
2. **Use `pydantic-ai-slim[openai]`, not `pydantic-ai`.** The full meta-package resolved 110 packages (anthropic, google, logfire, web...) and 2.55.0; slim gives 38. Spec §Dependencies says `pydantic-ai` -> change.
3. **`resource_limits` shape (spec §7 says "15 s / 128 MiB"):** it is a dict `CodeMode(resource_limits={'max_duration_secs': 15, 'max_memory': 128*1024*1024})` (bytes, int). Defaults 30 s / 256 MiB. Only these 2 keys; `'unlimited'` also accepted.
   - Semantics caveat: the duration allowance is **shared by consecutive `run_code` calls in one session** (reset only on session restart/crash/type error), so "15 s per snippet" is not exactly a per-run budget — it behaves per-run-ish. Keep the 90 s run timeout + `request_limit` as the real bound.
4. `CodeMode(max_tool_calls=...)` exists (default 100) — spec's 40 is valid. Imports: `from pydantic_ai_harness import CodeMode`; `from pydantic_ai.capabilities import AbstractCapability`; `from pydantic_ai import CallToolsNode, ModelRequestNode, RunContext`; `from pydantic_ai.result import FinalResult`; `from pydantic_graph import End`.
5. CodeMode exposes a single tool named `run_code` with arg `code: str` (all other tools become sandbox functions; with `tools='all'` the model is shown only `run_code`). FunctionModel script: `ToolCallPart('run_code', {'code': ...})`. Last expression value is the return value.
6. `RunResult.usage` is a **property** in 2.33 (`r.usage.requests`), not a method (`usage()` raises `TypeError`). Check phase-4/eval code.
7. With EndWhenSettled `result.output` is `None` (Agent output type str), so the service must read the answer from `deps` (outcome/clarifications), and the Agent plumbing for "no model text" must handle `None`. Final text answers (read-only questions) still arrive normally in `output`.
8. Spec does not mention `dynamic_catalog`; default False renders tool signatures in `run_code.description` (fine, same as PTC).

## TODO / needs access
- Pi 5 RAM (`docker stats` on the Pi): run `docker buildx build --platform linux/arm64 -t agent-spike --load agent/spike && docker run -d --name r agent-spike python ram.py`, sample `docker stats`. Needs Pi access. (Real arm64 CI runner `ubuntu-24.04-arm` also viable for the install check.)
- Live model runs (req 4, + 3d): one command per endpoint:
  `cd agent/spike && docker run --rm -e AGENT_LLM_BASE_URL=... -e AGENT_LLM_API_KEY=... -e AGENT_LLM_MODEL=... agent-spike python eval_quality.py`
  Needs: (a) a cloud OpenAI-compatible key (OpenRouter or similar) + model name, (b) a local model with tool support (e.g. `ollama pull qwen2.5:7b`, ~4.7 GB, needs user OK/Ollama running; from the container use `http://host.docker.internal:11434/v1`). Record odd 400s (shown verbatim in the note column) to decide on `compat.py`.
- Gate "≥ 1 model ≥ 7/10 without modifying requests" remains unverified.
- Spike pass criteria are heuristic keyword checks; eyeball failures before judging a model.

## Provisional recommendation
**GO on infra (reqs 1, 2-Mac, 3): Monty works on arm64, RAM ~85-125 MiB, all library hooks the plan relies on exist and behave as assumed.** Conditional on: pinning monty 0.0.21 + slim, and the still-open model-quality gate (req 4). Phase 2 contracts can start; do not close phase 1 / commit to the M1 model recommendation until live runs complete.

## Cập nhật 2026-10-10 — chạy YC 4 với endpoint thật (router local `localhost:20128`, OpenAI-compatible)

| Model | Kết quả |
| :--- | :--- |
| `oc/big-pickle` | 0/10 — 403 `FreeTierError: OpenCode's free tier can only be used from within OpenCode` |
| `ag/gemini-3-flash` | 0/10 — 403 upstream Antigravity "(reset after 2m)", sau đó router ngừng chạy |
| `kr/claude-opus-4.8`, `kr/claude-opus-4.7`, `kr/claude-opus-4.5`, `kr/claude-sonnet-5` | 400 `INVALID_MODEL_ID` từ upstream (probe 1 request) |
| **`kr/claude-sonnet-4.5`** | **7/10 — đạt ngưỡng ≥ 7** |

Chi tiết `kr/claude-sonnet-4.5` (req = số request model, sec = độ trễ):

| Câu | Loại | KQ | req | sec | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Hôm nay bé Na có những việc gì? | read | PASS | 3 | 10.9 | |
| Ai đang có nhiều việc chưa xong nhất? | read | FAIL | – | 22.4 | `UsageLimitExceeded` (request_limit=6) — model lặp `run_code` thay vì viết một chương trình |
| Trong danh sách đi chợ còn thiếu gì? | read | FAIL | 2 | 9.2 | liệt kê cả món đã mua — câu hỏi mơ hồ + bộ chấm khắt khe, không hẳn lỗi model |
| Nhà mình có mấy thành viên và ai là trẻ em? | read | PASS | 2 | 4.9 | |
| Việc nào của mẹ Lan hạn trong tuần này? | read | FAIL | 2 | 9.2 | trả "không có" — sai (Đóng tiền điện 12/10). Tool giả chỉ lọc `due` bằng đúng 1 ngày → model khó lọc theo khoảng. Tool thật (phase 4) có `due_from/due_to` |
| 3 câu đề xuất đi chợ | propose | PASS ×3 | 1 | 2.5–2.8 | proposal đúng, kết thúc sau 1 request (EndWhenSettled chạy đúng) |
| 2 câu mơ hồ | ambiguous | PASS ×2 | 1–2 | 2.3–7.2 | hỏi lại, không đề xuất |

**Quan sát**
- Router trả dạng stream (SSE) cả khi request không bật `stream` — pydantic-ai vẫn xử lý được, không cần `compat.py` cho model này.
- Độ trễ 2–22 s/lượt; câu đọc nhiều bước chậm nhất.
- Bài học cho phase 4: tool đọc phải có lọc theo **khoảng ngày**, instructions nên nói rõ "tuần này = thứ Hai–Chủ nhật" và khuyến khích **một** `run_code` cho câu tổng hợp.

**Kết luận:** GO cho phase 2 trở đi. Model khuyến nghị tạm: `kr/claude-sonnet-4.5` qua router của người dùng (người dùng chọn giữ endpoint này). Lưu ý vận hành: các route `oc/`, `ag/` bị upstream chặn, nhiều model `kr/` báo không hợp lệ → nguồn model này có thể đổi bất ngờ; agent phải xử lý lỗi model bằng fallback assistant cũ (đã có trong phase 5). Còn TODO: đo RAM trên Pi.

## Cập nhật 2 (2026-10-10) — chạy thêm model, đo RAM với model thật

Router `localhost:20128` chạy lại được → chạy `eval_quality.py` (venv local, cùng bản pin) cho thêm 4 model, song song.

| Model | Điểm | Độ trễ/câu | Ghi chú |
| :--- | :--- | :--- | :--- |
| **`kr/deepseek-3.2`** | **10/10** | 1.7–24 s | đúng cả câu tổng hợp ("ai nhiều việc nhất") bằng 2 request; chậm nhất ở câu đọc |
| `kr/qwen3-coder-next` | 8/10 | 0.8–19 s | sai "ai nhiều việc nhất" (trả "không có việc nào"); câu "còn thiếu gì" bị chấm FAIL do bộ chấm khắt khe (nhắc tới gạo) |
| `kr/claude-haiku-4.5` | 7/10 (lần 2 trong container: 9/10) | 1.4–11 s | nhanh nhất; lần 1 dính `UsageLimitExceeded` ở câu tổng hợp như sonnet-4.5 |
| `kr/claude-sonnet-4.5` | 7/10 (lần trước) | 2–22 s | xem bảng ở trên |
| `ag/gpt-oss-120b-medium` | 0/10 | – | 403 upstream Antigravity "(reset after 2m)" — lỗi nguồn, không phải model |

- **Không model nào cần sửa request** (không có 400 lạ do định dạng) → **không cần `compat.py`**.
- Điểm dao động giữa các lần chạy (haiku 7 → 9) → eval ở phase 9 nên chạy ≥ 2 lần/model.
- Hai lỗi lặp lại ở nhiều model đúng như bài học đã ghi: câu tổng hợp vượt `request_limit=6`, và lọc "tuần này". Bộ chấm heuristic, đã đọc tay các FAIL.

### RAM với model thật (container arm64 trên Mac, giới hạn `--memory=300m --memory-swap=300m`)
- `ram.py` (5 tool call song song × 20 lượt) dưới giới hạn 300 MiB: RSS 84→86 MiB, VmHWM 123 MiB, không OOM.
- `eval_quality.py` với `kr/claude-haiku-4.5` qua `host.docker.internal` (client openai/httpx thật, 10 câu): `docker stats` đỉnh **101.4 MiB**, `OOMKilled=false`.

### YC 3d — Ollama tool calling: HOÃN (deferred-to-deploy / không chặn)
Máy Mac này không cài Ollama/LM Studio (cổng 11434, 1234 không mở). Bằng chứng gián tiếp: CodeMode chỉ phơi **một** tool `run_code(code: str)` theo chuẩn function-calling OpenAI, và 2 model open-weight (`deepseek-3.2`, `qwen3-coder-next`) qua endpoint OpenAI-compatible đều gọi `run_code` đúng (8–10/10). Ollama `/v1` dùng cùng định dạng, nên rủi ro thấp; model nhỏ chạy local có thể kém (đã có trong Risk Assessment: chấp nhận model cloud). Kiểm khi có máy chạy Ollama:
`AGENT_LLM_BASE_URL=http://localhost:11434/v1 AGENT_LLM_API_KEY=ollama AGENT_LLM_MODEL=qwen2.5:7b .venv/bin/python eval_quality.py`

### YC 2 trên Pi 5: HOÃN sang phase 7 (deferred-to-deploy)
Không có quyền truy cập Pi từ máy này (không SSH config). Bằng chứng trên Mac (cùng `linux/arm64`, cùng image) đỉnh 101–123 MiB, tức < 50 % ngưỡng 300 MiB. Lưu ý khi đo trên Pi: kernel Pi 5 mặc định dùng trang 16 KiB nên RSS có thể cao hơn Mac một chút — vẫn còn dư nhiều. Phase 7 phải chạy:
`docker buildx build --platform linux/arm64 -t agent-spike --load agent/spike && docker run --rm --memory=300m agent-spike python ram.py` + `docker stats` lúc chạy 1 lượt thật; ghi số vào báo cáo phase 7. Nếu đỉnh ≥ 300 MiB → đặt `mem_limit` cao hơn hoặc bỏ bớt dependency trước khi phát hành M1.

## Chốt phase 1

| Tiêu chí Go | Kết quả |
| :--- | :--- |
| Monty chạy trên arm64 | **Đạt** — `linux/arm64` (aarch64) native trên Mac; wheel có sẵn, không build Rust. Pi thật: kiểm ở phase 7 |
| RAM đỉnh < 300 MiB | **Đạt trên Mac arm64** (101–123 MiB, chạy dưới cgroup 300 MiB không OOM). Pi: hoãn sang phase 7 |
| ≥ 1 model ≥ 7/10, không sửa request | **Đạt** — 4 model đạt (deepseek-3.2 10/10, qwen3-coder-next 8/10, haiku-4.5 7–9/10, sonnet-4.5 7/10), không cần `compat.py` |

**Quyết định: GO.** Phase 2 bắt đầu được.

**Version pin (đưa vào `agent/pyproject.toml` ở phase 3, commit kèm `uv.lock`):**
`pydantic-ai-slim[openai]==2.33.0`, `pydantic-ai-harness[codemode]==0.25.0`, `pydantic-monty==0.0.21` (bắt buộc pin chính xác), Python 3.12, base `python:3.12-slim`.

**Model đề xuất (ghi vào README phase 3; model cấu hình qua `AGENT_LLM_MODEL`, đổi không cần build lại):**
- Mặc định: `kr/deepseek-3.2` — điểm cao nhất (10/10), chậm hơn (đến ~24 s câu đọc nhiều bước).
- Phương án nhanh: `kr/claude-haiku-4.5` (≤ 11 s) — hợp câu đề xuất/hỏi lại.
- Người dùng trước đó đã chọn giữ router này với `kr/claude-sonnet-4.5`; vẫn dùng được (7/10). Quyết định tự động trong `--auto`: đề xuất deepseek-3.2 vì điểm, người dùng có thể đổi trong Thiết lập.
- Nguồn model là router của người dùng: route `ag/`, `oc/` bị upstream chặn, một số `kr/` báo `INVALID_MODEL_ID` → fallback sang assistant cũ (phase 5) là bắt buộc.

**Việc còn hoãn (không chặn Go):** đo RAM trên Pi 5 (phase 7), kiểm Ollama local (khi có máy chạy Ollama).
