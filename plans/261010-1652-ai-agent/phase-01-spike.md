# Phase 1 — Spike: Monty arm64, RAM, model

**Priority:** P1 (chặn mọi phase sau) · **Effort:** 4h · **Status:** Done — **GO** (2026-10-10). YC 1, 3 (a–c), 4 đạt (4 model ≥ 7/10, tốt nhất `kr/deepseek-3.2` 10/10, không cần `compat.py`); YC 2 đạt trên Mac arm64 (đỉnh 101–123 MiB), đo trên Pi hoãn sang phase 7; YC 3d (Ollama) hoãn — không chặn. Xem [reports/spike-s1.md](./reports/spike-s1.md)

## Context Links
- Spec §3.2 (S1), §5, §14 — [docs/ai-agent-spec.md](../../docs/ai-agent-spec.md)
- Tham chiếu: `everfit/foundry/workers/program-copilot-ptc/pyproject.toml` (pin `pydantic-ai-harness[codemode]>=0.25,<0.26`), `src/harness/cerebras_compat.py` (endpoint lệch chuẩn)

## Overview
Trả lời 4 câu trước khi viết code thật. Kết quả là `reports/spike-s1.md` với quyết định **go/no-go**.

## Requirements
1. **Monty trên arm64:** `uv pip install "pydantic-ai-harness[codemode]"` trong `python:3.12-slim` `linux/arm64` (build trên runner `ubuntu-24.04-arm` hoặc Pi) → import + chạy ví dụ `get_weather` của docs Code Mode.
2. **RAM:** RSS tiến trình agent lúc rảnh và lúc chạy 1 lượt có 5 tool call (đo bằng `docker stats` trên Pi 5). Ngưỡng chấp nhận: đỉnh < 300 MiB.
3. **API thư viện (bản pin):** `Agent(capabilities=[...])` + hook `after_node_run` (cho `EndWhenSettled`) tồn tại; `resource_limits` của Monty có tác dụng trên arm64; `history` qua `ModelMessagesTypeAdapter` round-trip JSON được; tool calling của Ollama chạy với CodeMode.
4. **Model:** 10 câu tiếng Việt (5 đọc, 3 đề xuất đi chợ, 2 mơ hồ) với tool giả (dữ liệu cứng) trên ≥ 2 endpoint OpenAI-compatible (vd 1 model lớn qua OpenRouter + 1 model nhỏ qua Ollama/LM Studio). Ghi: đúng/sai, số request, độ trễ, lỗi 400 lạ.

## Implementation Steps
1. Thư mục nháp `agent/spike/` (không commit vào image): `spike.py` dựng `Agent(OpenAIChatModel(...), capabilities=[CodeMode()])` + 4 tool giả (`list_members`, `list_tasks`, `list_shopping`, `propose_add_shopping_items`).
2. Dockerfile nháp `python:3.12-slim`, `uv sync`; `docker buildx build --platform linux/arm64`.
3. Chạy trên Pi: đo RAM; chạy 10 câu × mỗi model; ghi bảng.
4. Ghi `reports/spike-s1.md`: phiên bản đã pin, kết quả, model đề xuất ghi vào README, có cần `compat.py` không.

## Todo
- [x] Monty import + chạy trên arm64 (container `linux/arm64` trên Mac; Pi thật kiểm ở phase 7)
- [x] Số đo RAM rảnh / đỉnh — Mac arm64: rảnh 74–84 MiB, đỉnh 101–123 MiB dưới cgroup 300 MiB
- [x] Số đo RAM trên Pi 5 — **người dùng miễn (2026-10-11)** — không bắt buộc cho plan; nên làm khi triển khai lên Pi; trước đó: hoãn sang phase 7 (không truy cập được Pi từ máy làm spike)
- [ ] Ollama tool calling (YC 3d) — **hoãn** (máy không có Ollama); thay bằng 2 model open-weight qua endpoint OpenAI-compatible, đều chạy `run_code` đúng
- [x] Bảng 10 câu × ≥ 2 model (5 model, 4 đạt ≥ 7/10)
- [x] Quyết định go/no-go + version pin — **GO**; pin slim 2.33.0 / harness 0.25.0 / monty 0.0.21

## Success Criteria
Go khi: Monty chạy trên arm64, RAM đỉnh < 300 MiB, ít nhất 1 model ≥ 7/10 và không cần sửa request. No-go → cập nhật spec, báo người dùng.

## Risk Assessment
- Không có wheel arm64 → thử build từ source (Rust) trong stage builder; quá nặng → no-go.
- Model nhỏ chạy local quá kém → chấp nhận model cloud, ghi rõ trong README là dữ liệu rời máy.

## Next Steps
Phase 2.
