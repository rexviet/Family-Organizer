"""3 tool ĐỀ XUẤT Việc (phase 8): chỉ ghi operation vào `deps.outcome`, KHÔNG ghi dữ liệu thật.

Quyền kiểm sớm cho đúng với Node (Node vẫn kiểm lại lúc Duyệt, theo người bấm Duyệt):
- tạo: mọi vai trò; Con/Khách không tự đặt điểm thưởng;
- sửa: Con/Khách chỉ sửa việc mình tạo hoặc được giao — được giao (không phải người tạo) thì chỉ đổi trạng thái;
- xoá: chỉ Admin/Thành viên.
Trợ lý không hoàn thành/duyệt/trả việc: hợp đồng không có `completed`; việc đang chờ duyệt và trạng thái việc đã xong
không sửa qua trợ lý. `base` = `updatedAt` của việc lúc đề xuất.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from family_agent.harness.deps import AppDeps, ToolError, flag_failures
from family_agent.harness.tools.ask import STOP_MESSAGE
from family_agent.harness.tools.read import fetch_rows
from family_agent.harness.tools.records import (
    MAX_DESCRIPTION,
    MAX_TITLE,
    PENDING,
    clean_text,
    is_date_only,
    member_ids,
    parse_datetime,
    parse_day,
    resolve,
    short,
    stage,
)

_PRIORITIES: Final = ("low", "medium", "high")
_STATUSES: Final = ("todo", "in_progress")
_LIMITED: Final = ("child", "guest")


def _due(value: str) -> str:
    """Hạn: "YYYY-MM-DD" hoặc "YYYY-MM-DD HH:mm", ngày/giờ có thật."""
    if isinstance(value, str) and is_date_only(value):
        parse_day(value, "due_date")
    else:
        parse_datetime(value, "due_date")
    return value


async def _assignee(deps: AppDeps, value: str) -> str:
    if value not in await member_ids(deps):
        raise ToolError("assignee_id phải là id thành viên (xem bảng thành viên hoặc list_members).")
    return value


def _priority(value: str) -> str:
    if value not in _PRIORITIES:
        raise ToolError('priority phải là "low", "medium" hoặc "high".')
    return value


def _labeler(deps: AppDeps) -> Callable[[dict[str, Any]], str]:
    """"Tên — hạn HH:mm dd/MM — Người được giao" (người giao giúp phân biệt việc trùng tên trùng hạn)."""
    names = {m["id"]: m["fullName"] for m in deps.members}

    def label(t: dict[str, Any]) -> str:
        parts = [str(t.get("title", ""))]
        if t.get("dueDate"):
            parts.append(f"hạn {short(str(t['dueDate']))}")
        who = names.get(str(t.get("assigneeId") or ""))
        if who:
            parts.append(who)
        return " — ".join(parts)

    return label


async def _find(deps: AppDeps, ref: str, action: str) -> dict[str, Any] | None:
    rows = await fetch_rows(deps, "/api/tasks", "tasks")
    found = resolve(
        deps, ref, rows, kind="việc", action=action, list_tool="list_tasks", label=_labeler(deps),
        prefer=lambda t: t.get("status") != "completed",
    )
    if found is not None and (not isinstance(found.get("updatedAt"), str) or not found["updatedAt"]):
        raise ToolError(f'Việc "{found.get("title", "")}" thiếu thông tin cập nhật nên chưa đề xuất được.')
    return found


async def propose_create_task(
    ctx: RunContext[AppDeps],
    title: str,
    due_date: str | None = None,
    assignee_id: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    reward_points: int | None = None,
    is_shared: bool | None = None,
) -> str:
    """ĐỀ XUẤT tạo một việc mới. KHÔNG ghi thật: người dùng phải bấm Duyệt. Gọi xong lượt kết thúc.

    Args:
        title: tên việc, ngắn gọn.
        due_date: hạn "YYYY-MM-DD HH:mm" (hoặc "YYYY-MM-DD" = hết ngày đó).
        assignee_id: id người được giao (bảng thành viên). Bỏ trống = chưa giao.
        description: mô tả thêm (tuỳ chọn).
        priority: "low" | "medium" | "high".
        reward_points: điểm thưởng 0–1000 cho trẻ (chỉ người lớn đặt).
        is_shared: True = việc chung cả nhà (mặc định), False = riêng tư.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        op: dict[str, Any] = {"type": "task.create", "title": clean_text(title, MAX_TITLE, "Tên việc", required=True)}
        if description:
            op["description"] = clean_text(description, MAX_DESCRIPTION, "Mô tả")
        if due_date is not None:
            op["dueDate"] = _due(due_date)
        if assignee_id:
            op["assigneeId"] = await _assignee(deps, assignee_id)
        if priority is not None:
            op["priority"] = _priority(priority)
        if reward_points is not None:
            if deps.user.role in _LIMITED:
                raise ToolError("Con/Khách không tự đặt điểm thưởng cho việc.")
            if isinstance(reward_points, bool) or not isinstance(reward_points, int) or not 0 <= reward_points <= 1000:
                raise ToolError("reward_points phải là số nguyên từ 0 đến 1000.")
            op["rewardPoints"] = reward_points
        if is_shared is not None:
            op["isShared"] = bool(is_shared)
        stage(deps, op, target_key="taskId", name=op["title"])
        return f'Đã ghi nhận đề xuất tạo việc "{op["title"]}". {PENDING}'


async def propose_update_task(
    ctx: RunContext[AppDeps],
    task: str,
    title: str | None = None,
    due_date: str | None = None,
    assignee_id: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
) -> str:
    """ĐỀ XUẤT sửa một việc (đổi tên, dời hạn, giao người khác, đổi ưu tiên/trạng thái). Chỉ nêu trường cần đổi.

    KHÔNG ghi thật: người dùng phải bấm Duyệt. Không đánh dấu hoàn thành / duyệt việc được (làm trong app).
    Tên khớp nhiều việc thì tool tự hỏi lại người dùng. Gọi xong lượt kết thúc.

    Args:
        task: id việc (từ list_tasks) hoặc tên việc.
        title: tên mới.
        due_date: hạn mới "YYYY-MM-DD HH:mm"; chỉ "YYYY-MM-DD" thì giữ giờ cũ.
        assignee_id: id người được giao mới; "" = bỏ giao.
        description: mô tả mới.
        priority: "low" | "medium" | "high".
        status: "todo" (cần làm) | "in_progress" (đang làm).
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        found = await _find(deps, task, "sửa")
        if found is None:
            return STOP_MESSAGE
        name = str(found.get("title", ""))
        me, role = deps.user.id, deps.user.role
        creator, assignee = found.get("creatorId"), found.get("assigneeId")

        wanted: dict[str, Any] = {}
        if title is not None:
            wanted["title"] = clean_text(title, MAX_TITLE, "Tên việc", required=True)
        if description is not None:
            wanted["description"] = clean_text(description, MAX_DESCRIPTION, "Mô tả")
        if due_date is not None:
            due = _due(due_date)
            old_due = str(found.get("dueDate") or "")
            if is_date_only(due) and len(old_due) >= 16 and old_due[10] == " ":
                due = f"{due} {old_due[11:16]}"  # chỉ đổi ngày: giữ giờ cũ
            wanted["dueDate"] = due
        if assignee_id is not None:
            wanted["assigneeId"] = await _assignee(deps, assignee_id) if assignee_id else None
        if priority is not None:
            wanted["priority"] = _priority(priority)
        if status is not None:
            if status not in _STATUSES:
                raise ToolError('status chỉ là "todo" hoặc "in_progress"; hoàn thành/duyệt việc hãy làm trong app.')
            wanted["status"] = status

        if role in _LIMITED:
            if me not in (creator, assignee):
                raise ToolError(f'Bạn không có quyền sửa việc "{name}" (chỉ việc mình tạo hoặc được giao).')
            if creator != me and set(wanted) - {"status"}:
                raise ToolError(f'Với việc "{name}" được giao cho bạn, bạn chỉ đổi được trạng thái.')
        if found.get("pendingApproval"):
            raise ToolError(f'Việc "{name}" đang chờ duyệt — hãy duyệt hoặc trả lại trong mục Việc.')
        if "status" in wanted and found.get("status") == "completed":
            raise ToolError(f'Việc "{name}" đã hoàn thành — muốn mở lại hãy làm trong mục Việc.')

        changes = {k: v for k, v in wanted.items() if found.get(k) != v}
        if not changes:
            raise ToolError(f'Việc "{name}" đã đúng như vậy — không có thay đổi nào để đề xuất.')
        stage(deps, {"type": "task.update", "taskId": found["id"], "changes": changes,
                     "base": {"updatedAt": found["updatedAt"]}}, target_key="taskId", name=name)
        return f'Đã ghi nhận đề xuất sửa việc "{name}". {PENDING}'


async def propose_delete_task(ctx: RunContext[AppDeps], task: str) -> str:
    """ĐỀ XUẤT xoá một việc. KHÔNG ghi thật: người dùng phải bấm Duyệt. Chỉ Admin/Thành viên. Gọi xong lượt kết thúc.

    Args:
        task: id việc (từ list_tasks) hoặc tên việc; tên khớp nhiều việc thì tool tự hỏi lại.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        if deps.user.role not in ("admin", "member"):
            raise ToolError("Chỉ Admin/Thành viên được xoá công việc.")
        found = await _find(deps, task, "xoá")
        if found is None:
            return STOP_MESSAGE
        name = str(found.get("title", ""))
        stage(deps, {"type": "task.delete", "taskId": found["id"], "base": {"updatedAt": found["updatedAt"]}},
              target_key="taskId", name=name)
        return f'Đã ghi nhận đề xuất xoá việc "{name}". {PENDING}'


task_toolset: FunctionToolset[AppDeps] = FunctionToolset([
    propose_create_task, propose_update_task, propose_delete_task,
])
