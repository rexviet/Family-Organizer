"""EndWhenSettled — kết thúc lượt ngay sau bước tool đã ghi đề xuất hoặc câu hỏi (spec §2.3, mượn từ PTC).

Không có nó, sau `propose_*` model còn một request nữa để "tóm tắt" — tốn thêm một lượt LLM và dễ nói sai
("đã thêm rồi"). Vì lượt kết thúc không qua câu trả lời của model, `result.output` là None và `/run` đọc kết quả
từ `deps.outcome` / `deps.clarifications`; lời dẫn cho người dùng do code dựng.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import CallToolsNode, ModelRequestNode, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.result import FinalResult
from pydantic_graph import End

from family_agent.harness.deps import AppDeps


def is_settled(deps: AppDeps) -> bool:
    return not deps.outcome.is_empty() or not deps.clarifications.is_empty()


@dataclass
class EndWhenSettled(AbstractCapability[AppDeps]):
    """`after_node_run` trên CallToolsNode: tool đã chạy (deps có kết quả) nhưng request kế tiếp chưa gửi."""

    async def after_node_run(self, ctx: RunContext[AppDeps], *, node: Any, result: Any) -> Any:
        if not isinstance(node, CallToolsNode) or isinstance(result, End) or not is_settled(ctx.deps):
            return result
        if isinstance(result, ModelRequestNode):
            # Ghi nốt kết quả tool vào lịch sử (như pydantic-ai tự làm khi kết thúc) để không còn tool call mồ côi.
            ctx.messages.append(result.request)
        return End(FinalResult(None))
