"""CodeGuard — bao quanh tool `run_code` của CodeMode: ngân sách thời gian theo LƯỢT + đề xuất tất-cả-hoặc-không.

Vì sao cần (review phase 4): Monty chạy ĐỒNG BỘ trên event loop nên mọi giây chạy code là giây `/health` và các lượt
khác đứng. Giới hạn `max_duration_secs` của thư viện chỉ tính trong MỘT phiên: `restart: true` cấp lại ngân sách,
và nhiều `run_code` trong cùng một phản hồi của model chạy nối tiếp không có `await` xen giữa.
Nên ở đây:
- chỉ cho MỘT `run_code` mỗi phản hồi của model (các cái sau bị từ chối, model gộp vào một chương trình);
- không cho `restart` (phiên mới = ngân sách mới);
- cộng dồn thời gian thật đã chạy code của cả lượt; hết ngân sách thì từ chối `run_code` tiếp theo bằng câu cố định.
Một lần treo liên tục ≤ một ngân sách; cả lượt ≤ ngân sách + một lần chạy cuối (≤ một ngân sách nữa).

Atomic: nếu `run_code` lỗi giữa chừng (vd. propose_* thứ nhất thành công, cái thứ hai ném lỗi) thì hoàn tác
đề xuất và câu hỏi đã ghi trong lần chạy đó — lượt không được kết thúc với một đề xuất dở dang.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Final

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import ToolDefinition

from family_agent.harness.deps import AppDeps

RUN_CODE: Final = "run_code"
MSG_BUDGET: Final = (
    "Đã hết thời gian chạy code cho lượt này. Đừng gọi run_code nữa: hãy trả lời từ dữ liệu đã có "
    "hoặc nói rằng chưa tra cứu xong."
)
MSG_ONE_PER_STEP: Final = (
    "Mỗi lần trả lời chỉ chạy một run_code. Hãy gộp mọi việc vào MỘT chương trình (dùng asyncio.gather) rồi gọi lại."
)
MSG_ROLLED_BACK: Final = "Mọi đề xuất/câu hỏi trong lần chạy này đã bị HUỶ; hãy gọi lại đầy đủ."
MSG_NO_RESTART: Final = "Không dùng restart trong lượt này. Hãy sửa code và gọi run_code lại bình thường."


@dataclass
class CodeGuard(AbstractCapability[AppDeps]):
    async def wrap_tool_execute(
        self,
        ctx: RunContext[AppDeps],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: Any,
        handler: Any,
    ) -> Any:
        if call.tool_name != RUN_CODE:
            return await handler(args)
        deps = ctx.deps
        if isinstance(args, dict) and args.get("restart"):
            raise ModelRetry(MSG_NO_RESTART)
        if deps.code_spent_s >= deps.code_budget_s:
            raise ModelRetry(MSG_BUDGET)
        if ctx.run_step in deps.code_steps:
            raise ModelRetry(MSG_ONE_PER_STEP)
        deps.code_steps.add(ctx.run_step)

        ops = list(deps.outcome.operations)
        asked = list(deps.clarifications.entries)
        deps.tool_failed = False
        started = time.monotonic()

        def rollback() -> bool:
            changed = deps.outcome.operations != ops or deps.clarifications.entries != asked
            deps.outcome.operations = ops
            deps.clarifications.entries = asked
            return changed

        try:
            result = await handler(args)
        except Exception as e:
            if rollback():
                raise ModelRetry(f"{e}\n{MSG_ROLLED_BACK}") from None
            raise
        finally:
            deps.code_spent_s += time.monotonic() - started
        if deps.tool_failed:
            # Code của model tự bắt lỗi của propose_*/ask_user (try/except) nên run_code "thành công" — nhưng đề xuất
            # có thể đã dở dang. Không tin: hoàn tác hết và bắt model làm lại đầy đủ.
            rollback()
            raise ModelRetry(f"Có tool đề xuất/hỏi lại đã báo lỗi trong lần chạy này. {MSG_ROLLED_BACK}")
        return result
