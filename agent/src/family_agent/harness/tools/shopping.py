"""3 tool ĐỀ XUẤT đi chợ (spec §6.2): chỉ ghi operation vào `deps.outcome`, KHÔNG ghi dữ liệu thật.

Quy tắc: id phải có trong danh sách đi chợ vừa đọc (id lạ → hỏi lại người dùng, không bịa operation);
tên món gộp trùng theo không dấu/hoa thường; món đã có (chưa mua) trong danh sách thì bỏ qua và báo;
mỗi `shopping.add` ≤ 20 món, tổng ≤ 30, một lượt ≤ 10 operation (hợp đồng, kiểm lại bởi OutcomeSlot).
`base` của set_purchased/delete là `updatedAt` của món lúc đề xuất (hợp đồng contracts/README.md).
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from family_agent.harness.deps import AppDeps, ToolError, flag_failures
from family_agent.harness.outcome import OutcomeError
from family_agent.harness.tools.ask import STOP_MESSAGE
from family_agent.harness.tools.read import fetch_rows  # dùng chung bước đọc + kiểm định dạng
from family_agent.harness.vocab import fold

MAX_ITEMS_PER_OP = 20  # contracts: shopping.add.items.maxItems
MAX_NAME, MAX_QUANTITY, MAX_NOTE = 100, 50, 200
_PENDING = "Đây mới là ĐỀ XUẤT, đang chờ người dùng duyệt — chưa có gì được thay đổi thật."


class NewShoppingItem(TypedDict):
    name: str
    quantity: NotRequired[str]  # ví dụ "2 hộp", "1 kg"
    note: NotRequired[str]


def _clean(s: object, limit: int, what: str) -> str:
    if s is None:
        return ""
    if not isinstance(s, str):
        raise ToolError(f"{what} phải là chuỗi.")
    out = " ".join(s.split())
    if len(out) > limit:
        raise ToolError(f"{what} tối đa {limit} ký tự.")
    return out


def _parse_items(items: list[str | NewShoppingItem]) -> list[dict[str, str]]:
    """Chuẩn hoá + gộp trùng tên (không dấu, không phân biệt hoa thường); giữ thứ tự và tên gốc đầu tiên."""
    if not items:
        raise ToolError("Cần ít nhất một món.")
    merged: dict[str, dict[str, str]] = {}
    for raw in items:
        entry: dict[str, Any] = {"name": raw} if isinstance(raw, str) else dict(raw)
        name = _clean(entry.get("name"), MAX_NAME, "Tên món")
        if not name:
            raise ToolError("Tên món không được để trống.")
        quantity = _clean(entry.get("quantity"), MAX_QUANTITY, "Số lượng")
        note = _clean(entry.get("note"), MAX_NOTE, "Ghi chú")
        existing = merged.setdefault(fold(name), {"name": name})
        if quantity and "quantity" not in existing:
            existing["quantity"] = quantity
        if note and "note" not in existing:
            existing["note"] = note
    return list(merged.values())


def _check_conflicts(deps: AppDeps, ops: list[dict[str, Any]], names: dict[str, str] | None) -> None:
    staged = {op["itemId"]: op for op in deps.outcome.operations if "itemId" in op}
    for op in ops:
        prev = staged.get(op.get("itemId"))
        if prev is not None and prev != op:
            name = (names or {}).get(str(op["itemId"]), "này")
            raise ToolError(f"Món {name} đã có một đề xuất khác trong lượt này; mỗi món chỉ đề xuất một thay đổi.")


def _stage(deps: AppDeps, ops: list[dict[str, Any]], names: dict[str, str] | None = None) -> None:
    """Ghi tất cả hoặc không ghi gì: lỗi giữa chừng thì trả slot về như cũ.

    Một món chỉ được có MỘT thay đổi trong lượt (đề xuất y hệt cái cũ thì bỏ qua, khác thì báo lỗi) — tránh
    "đánh dấu đã mua" rồi "xoá" cùng một món, hoặc đặt true rồi false.
    """
    _check_conflicts(deps, ops, names)
    snapshot = list(deps.outcome.operations)
    try:
        for op in ops:
            deps.outcome.add(op)
    except OutcomeError as e:
        deps.outcome.operations = snapshot
        raise ToolError(str(e)) from None


def _names(items: list[dict[str, Any]]) -> str:
    return ", ".join(str(i["name"]) for i in items)


async def _items(deps: AppDeps) -> list[dict[str, Any]]:
    return await fetch_rows(deps, "/api/shopping", "shoppingItems")


async def propose_add_shopping_items(ctx: RunContext[AppDeps], items: list[str | NewShoppingItem]) -> str:
    """ĐỀ XUẤT thêm món vào danh sách đi chợ. KHÔNG ghi thật: người dùng phải bấm Duyệt.

    Tool tự gộp món trùng tên và bỏ qua món đã có (chưa mua) trong danh sách. Tối đa 30 món mỗi lượt.
    Gọi xong lượt sẽ kết thúc, đừng nói "đã thêm".

    Args:
        items: tên món (chuỗi) hoặc {"name": "Trứng", "quantity": "2 chục", "note": "..."}. name bắt buộc.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        wanted = _parse_items(items)
        have = {
            fold(str(i.get("name", ""))): str(i.get("name", "")) for i in await _items(deps) if not i.get("isPurchased")
        }
        staged = {
            fold(i["name"]): i["name"]
            for op in deps.outcome.operations if op["type"] == "shopping.add"
            for i in op["items"]
        }
        fresh = [w for w in wanted if fold(w["name"]) not in have and fold(w["name"]) not in staged]
        skipped = [have[fold(w["name"])] for w in wanted if fold(w["name"]) in have]
        again = [staged[fold(w["name"])] for w in wanted if fold(w["name"]) in staged and fold(w["name"]) not in have]
        note = f" Bỏ qua {len(skipped)} món đã có trong danh sách: {', '.join(skipped)}." if skipped else ""
        if again:
            note += f" Bỏ qua {len(again)} món đã đề xuất trước đó trong lượt này: {', '.join(again)}."
        if not fresh:
            return f"Các món này đã có sẵn trong danh sách đi chợ, không cần đề xuất thêm.{note}"
        _stage(deps, [
            {"type": "shopping.add", "items": fresh[i:i + MAX_ITEMS_PER_OP]}
            for i in range(0, len(fresh), MAX_ITEMS_PER_OP)
        ])
        return f"Đã ghi nhận đề xuất thêm {len(fresh)} món: {_names(fresh)}.{note} {_PENDING}"


def _ids(item_ids: list[str]) -> list[str]:
    ids: list[str] = []
    for raw in item_ids:
        i = raw.strip() if isinstance(raw, str) else ""
        if not i:
            raise ToolError("Mỗi item_id phải là id lấy từ list_shopping.")
        if i not in ids:
            ids.append(i)
    if not ids:
        raise ToolError("Cần ít nhất một item_id (lấy từ list_shopping).")
    return ids


def _resolve(
    deps: AppDeps, ids: list[str], items: list[dict[str, Any]], action: str, suggest: list[dict[str, Any]]
) -> list[dict[str, Any]] | None:
    """Trả các món theo id; nếu có id không tồn tại thì ghi câu hỏi lại (không bịa operation) và trả None."""
    by_id = {str(i.get("id")): i for i in items}
    if any(i not in by_id for i in ids):
        deps.clarifications.ask(
            f"Mình chưa xác định được món bạn muốn {action}. Bạn chọn món nào trong danh sách đi chợ?",
            [str(s.get("name", "")) for s in suggest],
        )
        return None
    found = [by_id[i] for i in ids]
    for f in found:
        if not isinstance(f.get("updatedAt"), str) or not f["updatedAt"]:
            raise ToolError(f"Món \"{f.get('name', '')}\" thiếu thông tin cập nhật nên chưa đề xuất được.")
    return found


def _purchase_op(f: dict[str, Any], purchased: bool) -> dict[str, Any]:
    return {"type": "shopping.set_purchased", "itemId": str(f["id"]), "purchased": purchased,
            "base": {"updatedAt": f["updatedAt"]}}


async def propose_set_purchased(ctx: RunContext[AppDeps], item_ids: list[str], purchased: bool) -> str:
    """ĐỀ XUẤT đánh dấu món là ĐÃ MUA (purchased=True) hoặc CHƯA MUA (purchased=False). Đặt giá trị, không lật.

    KHÔNG ghi thật: người dùng phải bấm Duyệt. Món đã ở đúng trạng thái sẽ được bỏ qua. Gọi xong lượt kết thúc.

    Args:
        item_ids: id món — PHẢI lấy từ list_shopping (include_purchased=True nếu cần món đã mua). Tối đa 10.
        purchased: True = đã mua, False = chưa mua.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        ids = _ids(item_ids)
        items = await _items(deps)
        suggest = [i for i in items if bool(i.get("isPurchased")) is (not purchased)]
        found = _resolve(deps, ids, items, "đánh dấu đã mua" if purchased else "đánh dấu chưa mua", suggest)
        if found is None:
            return STOP_MESSAGE
        # Kiểm xung đột trên MỌI món được nêu (kể cả món đã ở đúng trạng thái hiện tại nhưng đang có đề xuất ngược lại).
        names = {str(f["id"]): str(f.get("name", "")) for f in found}
        _check_conflicts(deps, [_purchase_op(f, purchased) for f in found], names)
        todo = [f for f in found if bool(f.get("isPurchased")) is not purchased]
        same = [f for f in found if f not in todo]
        note = f" Bỏ qua (đã ở trạng thái đó): {_names(same)}." if same else ""
        if not todo:
            return f"Các món đó đã ở đúng trạng thái, không cần thay đổi.{note}"
        _stage(deps, [_purchase_op(f, purchased) for f in todo], {str(f["id"]): str(f.get("name", "")) for f in todo})
        word = "đã mua" if purchased else "chưa mua"
        return f"Đã ghi nhận đề xuất đánh dấu {len(todo)} món là {word}: {_names(todo)}.{note} {_PENDING}"


async def propose_remove_shopping_items(ctx: RunContext[AppDeps], item_ids: list[str]) -> str:
    """ĐỀ XUẤT xoá món khỏi danh sách đi chợ. KHÔNG ghi thật: người dùng phải bấm Duyệt. Gọi xong lượt kết thúc.

    Args:
        item_ids: id món — PHẢI lấy từ list_shopping (include_purchased=True nếu cần món đã mua). Tối đa 10.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        ids = _ids(item_ids)
        items = await _items(deps)
        found = _resolve(deps, ids, items, "xoá", items)
        if found is None:
            return STOP_MESSAGE
        _stage(deps, [
            {"type": "shopping.delete", "itemId": str(f["id"]), "base": {"updatedAt": f["updatedAt"]}} for f in found
        ], {str(f["id"]): str(f.get("name", "")) for f in found})
        return f"Đã ghi nhận đề xuất xoá {len(found)} món: {_names(found)}. {_PENDING}"


shopping_toolset: FunctionToolset[AppDeps] = FunctionToolset([
    propose_add_shopping_items, propose_set_purchased, propose_remove_shopping_items,
])
