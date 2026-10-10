# Phase 3 — Agent service (Python) khung

**Priority:** P1 · **Effort:** 6h · **Status:** Pending

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
├── pyproject.toml          # uv; pin như PTC (cận trên mọi dependency)
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
- [ ] Skeleton + pin
- [ ] contract.py khớp vectors
- [ ] /health, /run, auth, semaphore, timeout
- [ ] Dockerfile arm64 chạy được
- [ ] README agent

## Success Criteria
`uv run pytest` xanh; image arm64 khởi động, `/health` đúng cả 2 trạng thái cấu hình.

## Security Considerations
Secret so sánh constant-time; không có endpoint nào ngoài `/health`, `/run`; không mount gì; key không bao giờ xuất hiện trong log/response.

## Next Steps
Phase 4.
