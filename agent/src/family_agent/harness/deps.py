"""AppDeps — trạng thái của MỘT lượt (tạo mới mỗi lượt, không dùng chung giữa người dùng).

Token người hỏi chỉ nằm trong header của `http`. Không có đường nào đưa nó vào instructions, tham số/kết quả
tool, thông điệp hay chuỗi lỗi: lỗi HTTP luôn được đổi thành câu tiếng Việt cố định.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final, TypedDict

import httpx
from pydantic_ai import ModelRetry

from family_agent.harness.clarify import ClarificationSink
from family_agent.harness.outcome import OutcomeSlot

# 9 endpoint đọc (spec §6.1) — khớp đúng đường dẫn, không id, không query (lọc làm phía agent).
ALLOWED_PATHS: Final = frozenset({
    "/api/users",
    "/api/tasks",
    "/api/plans",
    "/api/finance",
    "/api/finance/categories",
    "/api/finance/budgets",
    "/api/finance/recurring-bills",
    "/api/shopping",
    "/api/shopping/meal-plan/current",
})
HTTP_TIMEOUT_S: Final = 10.0
MAX_RESPONSE_BYTES: Final = 20 * 1024 * 1024  # /api/tasks có thể kèm ảnh base64; chặn phản hồi quá lớn


class ToolError(ModelRetry):
    """Lỗi của tool (tham số sai, không đọc được…). Thông điệp tiếng Việt cố định, model nhìn thấy để tự xử lý.

    Trong CodeMode mọi ngoại lệ của tool đều thành lỗi chạy code mà model đọc được (không làm hỏng lượt).
    """


@contextmanager
def flag_failures(deps: AppDeps) -> Iterator[None]:
    """Tool đề xuất/hỏi lại ném lỗi → đánh dấu để CodeGuard hoàn tác lần run_code này dù code có tự bắt lỗi."""
    try:
        yield
    except Exception:
        deps.tool_failed = True
        raise


class AppApiError(ToolError):
    """Lỗi khi đọc dữ liệu từ app (không bao giờ chứa URL/token)."""


class Member(TypedDict):
    id: str
    fullName: str
    role: str  # admin | member | child | guest
    relation: str  # nhãn quan hệ tiếng Việt ("Mẹ", "Con"…), "" nếu chưa đặt


@dataclass(frozen=True)
class UserInfo:
    id: str
    full_name: str
    role: str


def build_http_client(
    base_url: str,
    token: str,
    *,
    timeout: float = HTTP_TIMEOUT_S,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Client chỉ-GET tới app Node. Hook chặn MỌI request ngoài allowlist TRƯỚC khi gửi (kể cả host lạ)."""
    base = httpx.URL(base_url)

    async def guard(request: httpx.Request) -> None:
        url = request.url
        same_origin = (url.scheme, url.host, url.port) == (base.scheme, base.host, base.port)
        if request.method != "GET" or not same_origin or url.query or url.path not in ALLOWED_PATHS:
            raise AppApiError("Trợ lý chỉ được đọc dữ liệu qua các tool có sẵn.")

    return httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
        transport=transport,
        follow_redirects=False,
        event_hooks={"request": [guard]},
    )


_STATUS_MESSAGES: Final = {
    401: "Phiên truy cập của trợ lý đã hết hạn nên không đọc được dữ liệu. Hãy báo người dùng hỏi lại sau.",
    403: "Tài khoản của bạn không có quyền xem dữ liệu này. Không thử lại; hãy báo người dùng.",
}


@dataclass
class AppDeps:
    http: httpx.AsyncClient
    user: UserInfo
    today: str  # YYYY-MM-DD theo giờ VN (Monty không có datetime.now())
    weekday: str  # "Thứ Bảy"…
    members: list[Member] = field(default_factory=list)
    members_error: str | None = None
    outcome: OutcomeSlot = field(default_factory=OutcomeSlot)
    clarifications: ClarificationSink = field(default_factory=ClarificationSink)
    cache: dict[str, asyncio.Task[Any]] = field(default_factory=dict)
    # Ngân sách chạy code (Monty) của cả lượt — xem code_guard.py.
    code_budget_s: float = 15.0
    code_spent_s: float = 0.0
    code_steps: set[int] = field(default_factory=set)
    tool_failed: bool = False  # propose_*/ask_user vừa ném lỗi trong run_code hiện tại

    @property
    def today_date(self) -> date:
        return date.fromisoformat(self.today)

    async def get_json(self, path: str) -> Any:
        """GET một endpoint đọc, tối đa 1 lần/lượt (kể cả lỗi). Gọi đồng thời dùng chung một request đang bay."""
        task = self.cache.get(path)
        if task is None or task.cancelled():  # task bị huỷ thì không dùng lại
            task = asyncio.ensure_future(self._fetch(path))
            self.cache[path] = task
        # shield: một người chờ bị huỷ không kéo theo request mà người chờ khác đang dùng.
        return await asyncio.shield(task)

    async def aclose(self) -> None:
        """Huỷ request còn bay (nếu có), lấy hết ngoại lệ để không có cảnh báo, rồi đóng client."""
        for task in self.cache.values():
            task.cancel()
        await asyncio.gather(*self.cache.values(), return_exceptions=True)
        await self.http.aclose()

    async def _fetch(self, path: str) -> Any:
        try:
            async with self.http.stream("GET", path) as resp:
                if resp.status_code != 200:
                    raise AppApiError(
                        _STATUS_MESSAGES.get(resp.status_code)
                        or f"Ứng dụng báo lỗi (mã {resp.status_code}) khi đọc dữ liệu. Hãy thử lại sau."
                    )
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise AppApiError("Dữ liệu từ ứng dụng quá lớn nên chưa đọc được.")
                    chunks.append(chunk)
        except AppApiError:
            raise
        except httpx.HTTPError:
            raise AppApiError("Ứng dụng không phản hồi, chưa đọc được dữ liệu. Hãy thử lại sau.") from None
        try:
            return json.loads(b"".join(chunks))
        except ValueError:
            raise AppApiError("Dữ liệu từ ứng dụng không đúng định dạng.") from None
