---
title: "Trợ lý AI Agent (Pydantic AI + CodeMode)"
description: "Thay /api/assistant/chat bằng agent chạy container riêng, đọc/ghi Đi chợ, Việc, Lịch, Thu chi qua API có sẵn; agent chỉ đề xuất, người dùng Duyệt thì Node mới ghi."
status: released-pending-pi
priority: P2
effort: 68h
branch: main
tags: [feature, backend, frontend, infra, security, api]
blockedBy: []
blocks: []
created: 2026-10-10
---

# Trợ lý AI Agent

## Overview

Triển khai [docs/ai-agent-spec.md](../../docs/ai-agent-spec.md) (đã chốt D1–D4). Pha 0 (lọc quyền server) **đã xong** — commit `3f29f33`.
Ba mốc phát hành (minor), mỗi mốc dùng được độc lập:

| Mốc | Phase | Người dùng có gì |
| :--- | :--- | :--- |
| **M1** | 1–7 | Agent đọc 4 module + hội thoại + **ghi Đi chợ** qua card Duyệt |
| **M2** | 8 | Ghi **Việc + Lịch** (tạo/sửa/xoá) |
| **M3** | 9 | Ghi **Thu chi** + eval đầy đủ; cân nhắc gỡ assistant cũ |

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Spike: Monty arm64, RAM, model](./phase-01-spike.md) | Done — GO (RAM Pi đo ở phase 7) |
| 2 | [Hợp đồng operation + planHash](./phase-02-contracts.md) | Done |
| 3 | [Agent service (Python) khung](./phase-03-agent-service.md) | Done |
| 4 | [Agent harness: tool đọc, hỏi lại, đề xuất đi chợ](./phase-04-agent-harness.md) | Done — 346 pytest, model thật 9–10/10, 0 ghi |
| 5 | [Node: proxy, lưu trữ, Duyệt/apply](./phase-05-node-integration.md) | Done — E2E thật: đề xuất → Duyệt → món ở Đi chợ + SSE |
| 6 | [UI trợ lý + Thiết lập](./phase-06-ui.md) | Done — card Duyệt / chip hỏi lại / fallback; chạy tay Sáng+Tối+390 px |
| 7 | [Triển khai: compose, release 2 image, updater, CI](./phase-07-deploy.md) | Code done — updater 6 ca E2E local; chờ người dùng phát hành 1.2.0; thử + đo RAM trên Pi hoãn tới lần triển khai đầu |
| 8 | [Ghi Việc + Lịch (M2)](./phase-08-task-plan-writes.md) | Code done — 390 vitest + 395 pytest; đã phát hành trong **v1.2.0** (gộp M1–M3, fork rexviet, 2026-10-11); model thật `kr/deepseek-3.2` 7/10 & 8/10, 0 ghi — đạt |
| 9 | [Ghi Thu chi + eval (M3)](./phase-09-finance-writes-eval.md) | Code done — 411 vitest + 578 pytest; eval đợt 1: deepseek-3.2 77%/84%, haiku-4.5 75%/74% strict; đợt 2 đã sửa bộ câu + prompt/tool (`8bb4a81`), đo lại đầy đủ bị chặn (router hết hạn mức tháng) — **người dùng chấp nhận hiện trạng 2026-10-11** (84% strict, 86–91% trừ lỗi bộ chấm); 0 sai số tiền, 0 ghi ở mọi lần; đã phát hành trong **v1.2.0** (gộp M1–M3, fork rexviet, 2026-10-11); assistant cũ giữ lại |

**Trạng thái (2026-10-11):** mọi phase đã code xong và đã eval với model thật. Kết quả eval phase 9 (84% strict, 86–91% sau khi trừ lỗi bộ chấm) được **người dùng chấp nhận**; nên đo lại code cuối khi router có hạn mức (lệnh trong [báo cáo](./reports/phase-09-eval.md)). **Đã phát hành v1.2.0** (gộp M1–M3) trên fork `rexviet/Family-Organizer` — image `ghcr.io/rexviet/*:1.2.0`. Còn lại, đều do người dùng: đo RAM + thử cập nhật/Quay về trên Pi ở lần triển khai đầu (lưu ý compose/updater còn trỏ `happysmartlight`).
Phase 8 đạt; phase 9 an toàn đạt (0 sai số tiền, 0 ghi) ở mọi lần đo.

Thứ tự: 1 → 2 → (3 → 4) ‖ 5 → 6 → 7 → phát hành M1 → 8 → M2 → 9 → M3.
Phase 3–4 (Python) và 5 (Node) chạy song song được sau khi 2 xong — ranh giới là hợp đồng ở phase 2.

## Điều chỉnh so với spec (phát hiện khi lập plan)

- **Hội thoại + đề xuất lưu ở `data/agent.db` riêng**, không vào `FamilyOrganizerDB`: `sqliteSave` ghi lại *toàn bộ* collection mỗi lần ghi (`server/sqlite.ts:109`), nhét lịch sử chat vào sẽ làm mọi thao tác chậm dần. File riêng còn tự nằm ngoài bản sao lưu/snapshot cập nhật, và "Quay về" bản cũ chỉ đơn giản là bỏ qua file đó. Spec §9–10 cập nhật theo.

## Dependencies

- Python 3.12, `pydantic-ai` (OpenAI provider), `pydantic-ai-harness[codemode]` (Monty), `httpx`, `fastapi` + `uvicorn`, `uv`.
- Node: `better-sqlite3` (có sẵn), không thêm thư viện.
- Một endpoint LLM tương thích OpenAI có tool calling để chạy eval.

## Rủi ro chặn (go/no-go ở phase 1)

Monty không chạy trên linux/arm64, hoặc không model tương thích OpenAI nào trong tầm giá đạt ≥ 70% ở 10 câu thử → dừng, quay lại spec.

## Red-team (2026-10-10) — đã đưa vào phase

| Mức | Vấn đề | Xử lý |
| :--- | :--- | :--- |
| Critical | ID `Date.now()` trùng khi ghi nhiều bản ghi liền nhau + `writeRaw` nuốt lỗi → mất dữ liệu mà vẫn báo thành công | P5: hậu tố ngẫu nhiên + `applyBatch` một transaction, ghi lỗi thì ném |
| Critical | Gửi token đăng nhập (không hết hạn, toàn quyền) cho sidecar | P4–5: token agent 120 s, chỉ GET trên allowlist |
| High | Lịch không có `updatedAt`; đi chợ có `updatedAt` và toggle là **lật** | P2: hợp đồng đổi trước khi có M1 |
| High | Một biến version cho 2 image → quay về bản cũ làm hỏng `compose pull` cả stack | P7: `FAMILY_ORGANIZER_AGENT_VERSION` riêng |
| High | Apply không idempotent qua 2 DB | P5: `pending→applying` có điều kiện; khởi động lại → `failed` |
| High | `status: completed` qua agent = duyệt việc của trẻ | P2: cấm trong hợp đồng |
| High | **Lỗi có sẵn:** con/khách gửi kèm `comments` là sửa được việc người khác (`server.ts:915`) | P5 bước 1: bản vá riêng |
| High | Sửa giao dịch thiếu trường → về mặc định + xoá ảnh hoá đơn | P9: merge |
| Medium | Lộ token qua 422, history cắt hỏng, lệch phiên bản app/agent, agent lộ cho cả stack, spike thiếu kiểm API thư viện | P1, P3, P4, P5, P7 |
