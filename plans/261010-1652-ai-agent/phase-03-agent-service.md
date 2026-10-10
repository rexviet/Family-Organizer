# Phase 3 — Agent service (Python) khung

**Priority:** P1 · **Effort:** 6h · **Status:** Done (2026-10-10)

## Context Links
- Spec §3.1, §4, §5
- Kết quả phase 1 (`reports/spike-s1.md`) — version pin, base image

## Overview
Dịch vụ HTTP nhỏ, chưa có tool thật: cấu hình, xác thực nội bộ, `/health`, `/run` gọi một agent rỗng, Dockerfile arm64, test.

## Requirements
- **Chức năng**
  - `GET /health` → `{ok, llmConfigured, model, version}` (không lộ key/base_url).
  - `POST /run` (hợp đồng spec §4) → 401 nếu `X-Agent-Secret` sai (`hmac.compare_digest`), 503 nếu chưa cấu hình LLM, 422 nếu body sai.
  - Cấu hình từ env (`pydantic-settings`): `AGENT_LLM_BASE_URL`, `AGENT_LLM_API_KEY`, `AGENT_LLM_MODEL`, `AGENT_LLM_TEMPERATURE?`, `AGENT_LLM_TIMEOUT_S=60`, `AGENT_LLM_MAX_TOKENS?`, `AGENT_SHARED_SECRET` (bắt buộc, ≥ 32 ký tự), `APP_INTERNAL_URL`, `AGENT_VERSION` (CI truyền).
  - `contract.py`: canonical/planHash/fingerprint + validate — **pass cùng `agent/contracts/vectors.json`**.
- **Phi chức năng**
  - Một lượt ≤ 90 s (timeout cứng), tối đa 2 lượt đồng thời — đầy thì trả **429 ngay**, không xếp hàng.
  - `userToken` kiểu `SecretStr`; handler lỗi validation tuỳ biến **không** trả `input` (FastAPI 422 mặc định echo body → lộ token); test token không xuất hiện trong response/log.
  - Log JSON một dòng mỗi lượt: user id, kind, số tool call, ms, token; **không log nội dung**.
  - Chạy user không phải root, chỉ listen `0.0.0.0:3100` trong mạng compose (không publish port).

## Architecture
```
agent/
├── pyproject.toml          # uv; pin CHÍNH XÁC theo spike: pydantic-ai-slim[openai]==2.33.0,
│                           #   pydantic-ai-harness[codemode]==0.25.0, pydantic-monty==0.0.21
│                           #   (monty 1.1.0 đổi tên key resource_limits → mọi run_code lỗi)
├── uv.lock
├── Dockerfile              # python:3.12-slim, uv sync --frozen --no-dev, USER app
├── src/family_agent/
│   ├── __main__.py         # uvicorn
│   ├── settings.py
│   ├── app.py              # FastAPI: /health, /run, auth dependency
│   ├── model.py            # OpenAIChatModel + OpenAIProvider(base_url, api_key)
│   ├── contract.py
│   └── harness/            # phase 4
└── tests/{unit,contract}/
```

## Related Code Files
- Tạo toàn bộ `agent/` như trên; `agent/.dockerignore`; `agent/README.md` (biến env, chạy local, model đã kiểm chứng).

## Implementation Steps (TDD)
1. `uv init`, pin dependency theo spike.
2. RED → GREEN: `tests/contract/test_vectors.py` (đọc `../contracts/vectors.json`).
3. RED → GREEN: `tests/unit/test_app.py` với `httpx.ASGITransport`: secret sai → 401; thiếu LLM → 503 + `/health.llmConfigured=false`; body sai → 422.
4. `model.py`: dựng model từ settings; test bằng `pydantic_ai.models.test.TestModel` thay model thật (override qua dependency).
5. `/run` tạm trả `{"kind":"answer","reply":…}` từ agent rỗng (TestModel trong test).
6. Dockerfile + `docker build --platform linux/arm64`; `docker run` → `/health` 200.

## Todo
- [x] Skeleton + pin
- [x] contract.py khớp vectors
- [x] /health, /run, auth, semaphore, timeout
- [x] Dockerfile arm64 chạy được
- [x] README agent

## Kết quả (2026-10-10)

- `uv run pytest`: 122 test xanh (70 hợp đồng/vector + unit app/settings/model/main); `ruff check` + `mypy --strict` sạch.
- Image `docker build --platform linux/arm64`: chạy `aarch64`, user `app` (uid 10001), `HEALTHCHECK` healthy,
  RAM idle ~65 MiB. `/health` đúng cả 2 trạng thái; secret ngắn → exit 2 không in giá trị; `/docs` 404.

**Quyết định (--auto):**
- Hợp đồng `/run` dùng `agentToken` (theo spec §4 sau red-team) thay cho `userToken` ghi ở Requirements — `SecretStr`.
- Body `/run` tự đọc + validate (không để FastAPI tự parse) để **secret kiểm trước body** và 422 không bao giờ echo
  `input`; vẫn đăng ký handler `RequestValidationError` an toàn phòng hờ.
- Thêm `413 too_large` (`AGENT_MAX_BODY_BYTES`, mặc định 4 MiB), `504 timeout`, `502 llm_error`; giới hạn
  timeout/đồng thời cấu hình được qua `AGENT_RUN_TIMEOUT_S`, `AGENT_MAX_CONCURRENT_RUNS` (mặc định 90 s / 2).
- `/health` và `/run` trả thêm `contractVersion` (README hợp đồng yêu cầu). Tắt `/docs`, `/redoc`, `/openapi.json`.
- `contract.py` là bộ kiểm JSON Schema thu nhỏ đọc thẳng `operations.schema.json` (port từ `server/agentContract.ts`),
  không dùng thư viện `jsonschema` (vì `$` của `re` và `1.0` là integer). Image chép schema vào `/app/contracts`
  (`AGENT_CONTRACTS_DIR`).
- Thêm sẵn `ruff` + `mypy` (nhóm dev) để job CI của phase 7 chỉ việc gọi.
- `RunRequest`/`RunUser` để `extra="ignore"` — Node bản mới thêm trường không làm hỏng agent bản cũ.

**Sau code review (8.5/10, 0 critical) — đã sửa:** bỏ `populate_by_name` (High: làm pydantic-settings đọc cả env
không tiền tố `LLM_API_KEY`, `RUN_TIMEOUT_S`… → biến lạc trong stack đổi được endpoint/giới hạn); `TimeoutError`
từ bên trong model → 502, chỉ hết hạn của lượt mới là 504; client ngắt khi gửi body → 400 không traceback; huỷ lượt
→ trả slot + log `status 499`; log `{"event":"rejected","status"}` cho 401/413/422/429/503; secret phải ASCII in
được, không khoảng trắng hai đầu; OpenAI client `max_retries=1`; schema bắt buộc pattern có `^…$`.
**Chưa sửa (ghi nhận):** `uniqueItems` phía Node báo thêm lỗi "trùng" với số ngoài 2^53 (cả hai bên vẫn từ chối —
chỉ khác danh sách lỗi); base image chưa pin digest.

## Success Criteria
`uv run pytest` xanh; image arm64 khởi động, `/health` đúng cả 2 trạng thái cấu hình.

## Security Considerations
Secret so sánh constant-time; không có endpoint nào ngoài `/health`, `/run`; không mount gì; key không bao giờ xuất hiện trong log/response.

## Next Steps
Phase 4.
