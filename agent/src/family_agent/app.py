"""FastAPI: chỉ có GET /health và POST /run (spec §3.1, §4).

Thứ tự kiểm ở /run: secret (401) → LLM đã cấu hình (503) → body (413/422) → còn slot (429) → chạy (≤ timeout).
Không bao giờ trả/log nội dung hội thoại, token người hỏi, key hay base_url của LLM.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter
from pydantic_ai.models import Model
from starlette.requests import ClientDisconnect

from family_agent.contract import CONTRACT_VERSION
from family_agent.model import build_model
from family_agent.settings import Settings

log = logging.getLogger("family_agent.run")

ModelFactory = Callable[[Settings], Model]


# ---------------------------------------------------------------------------
# Hợp đồng /run (spec §4)
# ---------------------------------------------------------------------------


class RunUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=100)
    fullName: str = Field(max_length=200)  # noqa: N815 — tên trường theo JSON của Node
    role: Literal["admin", "member", "child", "guest"]


class RunRequest(BaseModel):
    # extra="ignore": Node bản mới thêm trường thì agent bản cũ vẫn chạy.
    model_config = ConfigDict(extra="ignore")

    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, Any]] = Field(default_factory=list, max_length=400)
    user: RunUser
    # Token ngắn hạn, chỉ GET (phase 5) — SecretStr để không lọt vào repr/log.
    agentToken: SecretStr = Field(min_length=1, max_length=4096)  # noqa: N815
    today: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    weekday: str = Field(min_length=1, max_length=20)


@dataclass
class TurnResult:
    kind: Literal["answer"]
    reply: str
    history: list[Any]
    usage: dict[str, int]


def _error(status: int, code: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": code, **extra}, status_code=status)


def _safe_errors(errors: list[Any]) -> list[dict[str, Any]]:
    """Lỗi validate KHÔNG kèm `input`/`ctx` — 422 mặc định của FastAPI echo body (lộ token)."""
    return [{"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in errors[:20]]


def _invalid(errors: list[Any]) -> JSONResponse:
    return _error(422, "invalid_request", errors=_safe_errors(errors))


class _BodyTooLarge(Exception):
    pass


async def _read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise _BodyTooLarge
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise _BodyTooLarge
        chunks.append(chunk)
    return b"".join(chunks)


def _load_history(raw: list[dict[str, Any]]) -> list[ModelMessage]:
    """History không parse được (vd. sau nâng cấp thư viện) → bỏ, không làm hỏng lượt."""
    if not raw:
        return []
    try:
        return ModelMessagesTypeAdapter.validate_python(raw)
    except ValidationError:
        log.warning(json.dumps({"event": "history_dropped", "messages": len(raw)}))
        return []


# ---------------------------------------------------------------------------
# Một lượt — phase 3: agent rỗng (chưa có tool). Phase 4 thay bằng harness thật.
# ---------------------------------------------------------------------------


def _instructions(req: RunRequest) -> str:
    return (
        "Bạn là trợ lý của gia đình dùng ứng dụng Family Organizer. Trả lời ngắn gọn bằng tiếng Việt.\n"
        f"Hôm nay là {req.today} ({req.weekday}), múi giờ Asia/Ho_Chi_Minh."
    )


async def run_turn(model: Model, req: RunRequest) -> TurnResult:
    agent = Agent(model, instructions=_instructions(req))
    result = await agent.run(req.message, message_history=_load_history(req.history))
    usage = result.usage  # thuộc tính trong pydantic-ai 2.33 (không gọi hàm)
    return TurnResult(
        kind="answer",
        reply=str(result.output),
        history=ModelMessagesTypeAdapter.dump_python(result.all_messages(), mode="json"),
        usage={
            "requests": usage.requests,
            "toolCalls": usage.tool_calls,
            "inputTokens": usage.input_tokens,
            "outputTokens": usage.output_tokens,
        },
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def create_app(settings: Settings, *, model_factory: ModelFactory = build_model) -> FastAPI:
    # Không có /docs, /redoc, /openapi.json — chỉ đúng 2 endpoint.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    model: Model | None = model_factory(settings) if settings.llm_configured else None
    expected_secret = settings.shared_secret.get_secret_value().encode("utf-8")
    inflight = 0

    @app.exception_handler(RequestValidationError)
    async def _on_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return _invalid(list(exc.errors()))

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "llmConfigured": model is not None,
            "model": settings.llm_model if model is not None else None,
            "version": settings.version,
            "contractVersion": CONTRACT_VERSION,
        }

    def reject(status: int, code: str, **extra: Any) -> JSONResponse:
        # Đếm được số lượt bị từ chối (vd. 429 vì bận) mà không log nội dung.
        log.info(json.dumps({"event": "rejected", "status": status}))
        return _error(status, code, **extra)

    @app.post("/run")
    async def run(request: Request) -> JSONResponse:
        nonlocal inflight
        provided = request.headers.get("x-agent-secret", "").encode("utf-8")
        if not hmac.compare_digest(provided, expected_secret):
            return reject(401, "unauthorized")
        if model is None:
            return reject(503, "llm_not_configured")

        try:
            raw = await _read_body(request, settings.max_body_bytes)
        except _BodyTooLarge:
            return reject(413, "too_large")
        except ClientDisconnect:  # Node bỏ ngang — không để uvicorn log traceback
            return reject(400, "client_disconnected")
        try:
            req = RunRequest.model_validate_json(raw)
        except ValidationError as e:
            return reject(422, "invalid_request", errors=_safe_errors(e.errors(include_input=False, include_url=False)))

        # Không xếp hàng: đầy thì trả ngay. Không có await giữa kiểm và tăng → an toàn trên event loop.
        if inflight >= settings.max_concurrent_runs:
            return reject(429, "busy")
        inflight += 1
        started = time.monotonic()
        entry: dict[str, Any] = {"event": "run", "userId": req.user.id, "role": req.user.role}
        deadline = asyncio.timeout(settings.run_timeout_s)
        try:
            async with deadline:
                turn = await run_turn(model, req)
        except asyncio.CancelledError:
            entry["status"] = 499  # lượt bị huỷ từ ngoài (client ngắt / server tắt)
            raise
        except Exception as e:  # lỗi model/endpoint LLM — chỉ log tên lớp, thông điệp có thể chứa URL/key
            if isinstance(e, TimeoutError) and deadline.expired():
                entry |= {"status": 504, "error": "timeout"}
                return _error(504, "timeout")
            entry |= {"status": 502, "error": type(e).__name__}
            return _error(502, "llm_error")
        else:
            entry |= {"status": 200, "kind": turn.kind, **turn.usage}
            return JSONResponse({
                "kind": turn.kind,
                "reply": turn.reply,
                "history": turn.history,
                "usage": turn.usage,
                "contractVersion": CONTRACT_VERSION,
            })
        finally:
            inflight -= 1
            entry["ms"] = round((time.monotonic() - started) * 1000)
            log.info(json.dumps(entry, ensure_ascii=False))

    return app
