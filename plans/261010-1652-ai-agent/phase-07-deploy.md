# Phase 7 — Triển khai: compose, release 2 image, updater, CI → phát hành M1

**Priority:** P1 · **Effort:** 8h · **Status:** Done — đã phát hành v1.2.0 (fork); kiểm trên Pi được người dùng miễn

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
- [x] Compose + env
- [x] updater.sh v3 + 4 kịch bản thử (thử thêm: thiếu tag agent, restart)
- [x] updater.ts đọc trạng thái agent
- [x] CI job agent (chưa chạy trên GitHub — chưa push)
- [x] release.yml 2 image, owner động (chưa chạy — chạy khi có tag)
- [x] README + CHANGELOG (mục `[1.2.0]` là **bản nháp**, sửa ngày lúc phát hành)
- [x] Thử trên Pi — **người dùng miễn (2026-10-11)** — không bắt buộc cho plan; nên làm khi triển khai lên Pi; trước đó: hoãn tới lần triển khai đầu (không có quyền vào Pi từ máy dev)
- [x] Đo RAM agent trên Pi 5 (hoãn từ phase 1) — **người dùng miễn (2026-10-11)** — không bắt buộc cho plan; nên làm khi triển khai lên Pi. Trên Pi, sau khi agent chạy:
      `docker stats --no-stream family_organizer_agent` lúc rảnh, rồi hỏi trợ lý 1 câu đọc nhiều bước và chạy
      `for i in $(seq 1 30); do docker stats --no-stream --format '{{.MemUsage}}' family_organizer_agent; sleep 1; done`
      + `docker inspect -f '{{.State.OOMKilled}}' family_organizer_agent`. Đỉnh phải < 300 MiB (mem_limit 384m).
      Số đo Mac arm64 làm mốc: rảnh 66 MiB (image thật, phase 7), đỉnh 101–123 MiB (spike).
- [ ] Phát hành M1 — **chờ người dùng phát hành**: `npm run release -- 1.2.0` → `git push && git push --tags`

## Kết quả (2026-10-10)

**Quyết định (--auto):**
- Agent nằm trong **compose profile `agent`** ở bản cài riêng: `docker compose up -d` mặc định không chạy container
  thiếu secret (agent thoát exit 2 → lặp khởi động). Bật bằng `COMPOSE_PROFILES=agent` trong `.env`; updater đọc `.env`
  nên `dc config --services` tự thấy agent. Stack liu-homelab thêm service bằng tay, không cần profile.
- `state.env` thêm giá trị `kept` (ngoài ok|failed|absent): bản đích < 1.2.0 hoặc app quay về → agent giữ nguyên.
- Agent chỉ đụng tới **sau khi app khỏe** → app quay về thì agent chưa đổi gì, khỏi phải quay về agent.
  Agent không healthy sau khi lên bản mới → để nguyên (image có thật, compose không hỏng), chỉ ghi `failed`;
  không kéo được image → trả `FAMILY_ORGANIZER_AGENT_VERSION` về giá trị cũ.
- `ver_ge` so số major.minor.patch, bỏ hậu tố `-rc…` (release.yml build agent cho mọi tag nên bản rc cũng có image).
- HEALTHCHECK agent thêm `--start-interval=3s` (agent healthy sau ~5 s thay vì ~30 s).
- Compose giữ owner image `happysmartlight` (compose không đổi chữ thường được); release.yml lấy owner động.

**Bằng chứng (máy Mac arm64, Docker 29.4 / Compose 5.1):**
- `npm run lint` ✓ · `npm test` 347 ✓ · `npm run build` ✓ · `sh -n deploy/updater.sh` ✓ (cả busybox) ·
  agent `ruff` ✓ `mypy src` ✓ `pytest` 346 ✓ · `gen_vectors.py --check` ✓ · `docker compose config -q` có/không profile ✓
- Updater E2E: registry local + image giả + `updater.sh` thật trong `docker:28-cli`, stack có service "khác":
  | Ca | Kết quả |
  | :--- | :--- |
  | (a) 1.1.0→1.2.0 có agent | ok, `agent=ok`, cả hai lên 1.2.0, service khác không bị đụng |
  | (b) không bật profile | ok, `agent=absent`, biến agent không đổi |
  | (c) agent 1.3.0 unhealthy | app 1.3.0 ok, `agent=failed`, không rollback |
  | (c') không có tag agent 1.2.5 | app ok, `agent=failed`, biến agent trả về 1.3.0, `docker compose pull` cả stack exit 0 |
  | (d) app 1.4.0 hỏng | `rolled_back` về 1.2.5, `agent=kept`, agent không đổi |
  | (e) Quay về 1.1.0 khi có agent | ok, `agent=kept`, `docker compose pull` cả stack exit 0 (không "manifest unknown") |
  | restart | ok |
- Build thật cả 2 image bằng `docker-compose.yml` của repo (profile agent): app→agent `/health` qua tên service ✓,
  agent→app `/api/health` ✓, agent ra Internet qua `fo-egress` ✓, container khác trên mạng default **không** phân giải
  được agent ✓, `/run` sai secret → 401 ✓, agent uid 10001, CapEff 0 ✓, RAM rảnh 66.5 MiB / 384 MiB.
- Đã dọn mọi container/image/network/registry thử.

**Code review (8/10, 0 critical) → đã sửa:**
- H1 package GHCR mới mặc định private → Pi không kéo được `:latest` của agent, `compose pull` cả stack lỗi:
  release.yml thêm bước kiểm `docker manifest inspect` **không đăng nhập** cho cả 2 image trước khi tạo Release
  (lần đầu: đổi package `family-organizer-agent` sang Public rồi chạy lại job) — ghi trong CLAUDE.md.
- M1 build/push agent **trước** app (agent lỗi build thì chưa có tag app nào).
- M2 agent không healthy → trả biến về + `up -d` lại agent bản trước (thử lại ca (c): agent về 1.2.0).
- M3 `agent=` reset mỗi lượt (restart/immich → trống; thử lại: restart → `agent=`).
- M4 README: bản cài riêng phải lấy `docker-compose.yml` mới trước; `COMPOSE_PROFILES` phải ở `.env`.
- M5 chỉ thay script updater khi lượt cập nhật `ok` (thử lại: app hỏng + `script=` → script không bị thay).
- L2 image agent không có HEALTHCHECK → `running` là đủ.
- Chưa làm (ghi nhận): L3 fork vẫn trỏ `happysmartlight` ở compose/README/bootstrap; L4 `read_only`/`pids_limit` cho agent
  (cần thử trên Pi).

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
