# Phase 7 — Triển khai: compose, release 2 image, updater, CI → phát hành M1

**Priority:** P1 · **Effort:** 8h · **Status:** Pending

## Context Links
- Spec §3.1, §3.2; CLAUDE.md (phát hành + ràng buộc updater)
- `docker-compose.yml`, `.env.example`, `.github/workflows/{ci,release}.yml`, `deploy/updater.sh` (`do_update` dòng 271, `health_wait` 125, rollback ~330), `server/updater.ts`

## Overview
Đưa container agent vào cài đặt riêng và stack liu-homelab; mỗi bản phát hành build 2 image cùng tag; updater cập nhật/quay về cả hai mà không phá stack cũ.

## Requirements
- **Compose (repo):** service `family-organizer-agent` như spec §3.1, nhưng image dùng **biến riêng** `${FAMILY_ORGANIZER_AGENT_VERSION:-latest}` (không `ports`, không volume, `mem_limit` theo spike); app thêm `AGENT_URL`, `AGENT_SHARED_SECRET`. `.env.example` thêm 4 biến + lệnh sinh secret (`openssl rand -hex 32`).
- **release.yml:** thêm bước build-push `agent/` → `ghcr.io/<owner>/family-organizer-agent:{version,minor,latest}`, `build-args: AGENT_VERSION`. Owner image lấy từ biến (`${{ github.repository_owner }}` chữ thường) thay vì cứng `happysmartlight` — fork phát hành được.
- **ci.yml:** job `agent` song song: `astral-sh/setup-uv`, `uv sync --frozen`, `ruff check`, `mypy src`, `pytest` (không chạy eval). Giữ `sh -n deploy/updater.sh`.
- **updater.sh** (`SCRIPT_VERSION=3`):
  - `AGENT_SERVICE="${AGENT_SERVICE-family-organizer-agent}"`; `has_agent()` = có trong `dc config --services`.
  - `do_update`: pull cả hai (agent chỉ khi `has_agent`); up app → `health_wait` như cũ; rồi up agent → chờ agent healthy (healthcheck Docker của container, tối đa 120 s). Agent không lên → **không** rollback app; `state.env` thêm `agent=failed|ok|absent`.
  - **Biến phiên bản riêng `FAMILY_ORGANIZER_AGENT_VERSION`** (H3): updater chỉ đặt biến này khi bản đích ≥ `AGENT_MIN_VERSION` (bản đầu tiên có image agent). Quay về bản cũ hơn → **giữ nguyên** agent ở bản hiện tại (hợp đồng có `contractVersion`; lệch thì app cũ đơn giản không dùng agent). Không bao giờ để compose trỏ tới tag agent không tồn tại — nếu không, `docker compose pull/up` cả stack liu-homelab (Immich…) sẽ lỗi "manifest unknown".
  - Pull/up agent lỗi → ghi log + `agent=failed`, **không** dừng cập nhật hay rollback của app.
  - `prune_images` dọn cả image agent cũ.
  - Dockerfile agent có `HEALTHCHECK` gọi `/health` (python one-liner, không cần curl).
- **server/updater.ts:** đọc thêm `agent=` từ `state.env`, hiện cảnh báo trong trang Cập nhật nếu `failed`.
- **Tài liệu:** README mục "Trợ lý nâng cao" (thêm service vào stack liu-homelab bằng tay, biến env, model đã kiểm chứng); CHANGELOG `## [1.2.0]` tiếng Việt cho gia đình.

## Related Code Files
- Sửa: `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `deploy/updater.sh`, `server/updater.ts`, `server/updater.test.ts`, `README.md`, `CHANGELOG.md`
- Sửa: `agent/Dockerfile` (HEALTHCHECK)

## Implementation Steps
1. Compose + `.env.example`; `docker compose up -d --build` local (Mac) → app gọi được agent qua tên service.
2. updater.sh: sửa + `sh -n`; thử trên stack local: (a) có agent, cập nhật lên tag thử; (b) không có agent → bỏ qua; (c) agent hỏng → app vẫn lên, `agent=failed`; (d) app hỏng → app quay về, agent giữ nguyên, `docker compose pull` cả stack vẫn chạy; (e) "Quay về" 1.1.0 khi stack có agent → không lỗi manifest.
3. `server/updater.ts` + test đọc `agent=`.
4. release.yml/ci.yml; push nhánh → CI xanh (cả job agent).
5. Thử trên Pi (stack liu-homelab): thêm service bằng tay theo README, cập nhật, quay về.
6. CHANGELOG + `npm run release -- 1.2.0` → **hỏi người dùng trước khi push tag**.

## Todo
- [ ] Compose + env
- [ ] updater.sh v3 + 4 kịch bản thử
- [ ] updater.ts đọc trạng thái agent
- [ ] CI job agent
- [ ] release.yml 2 image, owner động
- [ ] README + CHANGELOG
- [ ] Thử trên Pi
- [ ] Phát hành M1 (sau khi người dùng đồng ý)

## Success Criteria
4 kịch bản updater đúng; CI xanh; trên Pi cập nhật + quay về hoạt động với cả stack có và không có agent.

## Risk Assessment
- Updater là phần nhạy cảm (cầm docker socket) → thay đổi nhỏ nhất có thể, giữ danh sách service cố định, không nhận tên service từ app.
- Bản updater mới tự tải từ tag → bản cũ trên máy vẫn cập nhật được lên 1.2.0 (chỉ chưa biết agent) → lần cập nhật kế tiếp mới quản agent; ghi rõ trong CHANGELOG.

## Security Considerations
Secret chỉ ở `.env` (gitignored); agent không publish port; image agent chạy non-root.

## Next Steps
Phase 8 (M2).

## Mạng riêng (M7)
Compose thêm network `fo-agent` (internal) chỉ app + agent tham gia; agent **không** nằm ở network mặc định của stack (Immich, Home Assistant… không gọi được agent). Agent cần ra Internet tới LLM → thêm network `fo-egress` (không internal) chỉ agent dùng, hoặc dùng network mặc định nếu LLM chạy trong cùng máy — ghi rõ 2 cách trong README.
