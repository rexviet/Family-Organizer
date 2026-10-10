"""3 tool ĐỀ XUẤT Thu chi (phase 9): chỉ ghi operation vào `deps.outcome`, KHÔNG ghi dữ liệu thật.

- Chỉ Admin/Thành viên (khớp POST/DELETE /api/finance); Con/Khách bị chặn ngay, không gửi request nào.
- Số tiền đổi bằng `money.parse_vnd` ("250k", "1tr2"…) — model không tự tính; nhập nhằng → lỗi để model hỏi lại.
- Khoản CHI: hạng mục phải là hạng mục đang dùng (mặc định chưa ẩn hoặc gia đình tự thêm); không rõ → hỏi lại kèm lựa
  chọn. Khoản THU: hạng mục là chữ tự do như app (gợi ý "Lương tháng"…); thiếu → hỏi lại.
- Giao dịch không có `updatedAt` → `base` = fingerprint bản ghi GỐC. Bản ghi cũ có số tiền lẻ làm fingerprint lỗi →
  không đề xuất được (báo người dùng sửa trong app), không làm tròn.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Final

from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from family_agent.contract import fingerprint
from family_agent.harness.deps import AppApiError, AppDeps, ToolError, flag_failures
from family_agent.harness.money import parse_vnd
from family_agent.harness.tools.ask import STOP_MESSAGE
from family_agent.harness.tools.read import fetch_rows
from family_agent.harness.tools.records import PENDING, clean_text, parse_day, resolve, short, stage
from family_agent.harness.vocab import BUILTIN_CATEGORIES, INCOME_CATEGORIES, fold

_TX_TYPES: Final = ("income", "expense")
_ACCOUNTS: Final = ("cash", "bank", "e_wallet")
MAX_TX_DESCRIPTION: Final = 500
MAX_CATEGORY: Final = 100
MAX_CATEGORY_OPTIONS: Final = 10
RECENT_DAYS: Final = 31  # tên khớp nhiều giao dịch → ưu tiên giao dịch trong 31 ngày gần đây


def money(amount: object) -> str:
    """250000 → "250.000₫" (khớp `money` của preview Node)."""
    if isinstance(amount, bool) or not isinstance(amount, int | float):
        return str(amount)
    n = round(amount)
    return f"{n:,}₫".replace(",", ".")


def _guard_role(deps: AppDeps) -> None:
    if deps.user.role not in ("admin", "member"):
        raise ToolError("Chỉ Admin/Thành viên được ghi hoặc sửa thu chi.")


async def _expense_categories(deps: AppDeps) -> list[tuple[str, str]]:
    """(id, nhãn) các hạng mục chi đang dùng: mặc định chưa ẩn + hạng mục gia đình tự thêm."""
    data = await deps.get_json("/api/finance/categories")
    if not isinstance(data, dict):
        raise AppApiError("Dữ liệu từ ứng dụng không đúng định dạng.")
    hidden = {h for h in data.get("hiddenBuiltinCategories") or [] if isinstance(h, str)}
    out = [(cid, label) for cid, label in BUILTIN_CATEGORIES.items() if cid not in hidden]
    for c in data.get("customCategories") or []:
        if isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] and isinstance(c.get("label"), str):
            out.append((c["id"], c["label"]))
    return out


async def _expense_category(deps: AppDeps, value: str | None) -> tuple[str, str] | None:
    """(id, nhãn) hạng mục chi khớp id hoặc nhãn (không dấu). Không rõ → hỏi lại, trả None."""
    cats = await _expense_categories(deps)
    key = fold(value or "")
    if key:
        for cid, label in cats:
            if key in (fold(cid), fold(label)):
                return cid, label
    # Lựa chọn (tối đa 10): hạng mục gia đình tự thêm trước, rồi mặc định; "Khoản khác" luôn ở cuối nếu còn dùng.
    other = [label for cid, label in cats if cid == "other"]
    rest = [label for cid, label in cats if cid not in BUILTIN_CATEGORIES] + [
        label for cid, label in cats if cid in BUILTIN_CATEGORIES and cid != "other"
    ]
    deps.clarifications.ask(
        "Khoản chi này thuộc hạng mục nào?" if not key else f'Không có hạng mục chi "{value}" — bạn chọn hạng mục nào?',
        rest[: MAX_CATEGORY_OPTIONS - len(other)] + other,
    )
    return None


def _income_category(deps: AppDeps, value: str | None) -> str | None:
    text = clean_text(value, MAX_CATEGORY, "Nguồn thu")
    if text:
        return text
    deps.clarifications.ask("Khoản thu này là nguồn thu nào?", list(INCOME_CATEGORIES))
    return None


def _account(value: str) -> str:
    if value not in _ACCOUNTS:
        raise ToolError('account phải là "cash" (tiền mặt), "bank" (ngân hàng) hoặc "e_wallet" (ví điện tử).')
    return value


def _label(t: dict[str, Any]) -> str:
    """"Mô tả — 250.000₫ — dd/MM" (số tiền + ngày phân biệt các giao dịch cùng mô tả)."""
    return f"{t.get('description', '')} — {money(t.get('amount'))} — {short(str(t.get('date') or ''))}"


async def _find(deps: AppDeps, ref: str, action: str) -> tuple[dict[str, Any], str] | None:
    """(giao dịch gốc, fingerprint). Mơ hồ → None (đã hỏi lại)."""
    rows = await fetch_rows(deps, "/api/finance", "transactions")
    since = (date.fromisoformat(deps.today) - timedelta(days=RECENT_DAYS)).isoformat()
    found = resolve(
        deps, ref, rows, kind="giao dịch", action=action, list_tool="search_transactions", label=_label,
        prefer=lambda t: str(t.get("date") or "")[:10] >= since, name_key="description",
    )
    if found is None:
        return None
    try:
        return found, fingerprint("transaction", found)
    except ValueError:  # số tiền lẻ/kiểu lạ: hai bên không tính được cùng một dấu vân tay
        raise ToolError(
            f'Giao dịch "{found.get("description", "")}" có số tiền lẻ/dữ liệu lạ nên trợ lý không đề xuất được — '
            "hãy sửa trực tiếp trong mục Thu chi."
        ) from None


async def propose_create_transaction(
    ctx: RunContext[AppDeps],
    tx_type: str,
    amount: str | int,
    category: str,
    description: str | None = None,
    date: str | None = None,
    account: str | None = None,
) -> str:
    """ĐỀ XUẤT ghi một khoản thu/chi. KHÔNG ghi thật: người dùng phải bấm Duyệt. Gọi xong lượt kết thúc.

    Args:
        tx_type: "expense" (khoản chi) hoặc "income" (khoản thu).
        amount: số tiền ĐÚNG NGUYÊN VĂN người dùng nói, ví dụ "250k", "1tr2", "1,5 triệu", "250.000" — tool tự đổi
            ra đồng. Đừng tự nhân/chia.
        category: khoản chi: id hoặc nhãn hạng mục (food = Ăn uống…, hạng mục tự thêm xem list_expense_categories);
            khoản thu: nguồn thu, ví dụ "Lương tháng", "Tiền thưởng". Không rõ thì để "" — tool tự hỏi lại.
        description: nội dung ngắn (mặc định = tên hạng mục).
        date: ngày "YYYY-MM-DD" (mặc định hôm nay).
        account: "cash" (tiền mặt) | "bank" (ngân hàng) | "e_wallet" (ví điện tử); bỏ trống = mặc định của app.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        _guard_role(deps)
        if tx_type not in _TX_TYPES:
            raise ToolError('tx_type phải là "expense" (chi) hoặc "income" (thu).')
        value = parse_vnd(amount)
        day = parse_day(date, "date").isoformat() if date is not None else deps.today
        acct = _account(account) if account is not None else None
        desc = clean_text(description, MAX_TX_DESCRIPTION, "Nội dung")
        if tx_type == "expense":
            cat = await _expense_category(deps, category)
            if cat is None:
                return STOP_MESSAGE
            cat_id, cat_label = cat
        else:
            income = _income_category(deps, category)
            if income is None:
                return STOP_MESSAGE
            cat_id = cat_label = income
        op: dict[str, Any] = {
            "type": "finance.create", "txType": tx_type, "amount": value, "category": cat_id, "date": day,
            "description": desc or cat_label,
        }
        if acct is not None:
            op["account"] = acct
        stage(deps, op, target_key="txId", name=op["description"])
        kind = "khoản chi" if tx_type == "expense" else "khoản thu"
        return f'Đã ghi nhận đề xuất ghi {kind} {money(value)} "{op["description"]}" ngày {short(day)}. {PENDING}'


async def propose_update_transaction(
    ctx: RunContext[AppDeps],
    transaction: str,
    amount: str | int | None = None,
    category: str | None = None,
    date: str | None = None,
    description: str | None = None,
    account: str | None = None,
) -> str:
    """ĐỀ XUẤT sửa một giao dịch thu chi. Chỉ nêu trường cần đổi; các trường khác (kể cả ảnh hoá đơn) giữ nguyên.

    KHÔNG ghi thật: người dùng phải bấm Duyệt. Không đổi được thu ↔ chi (xoá rồi ghi lại). Mô tả khớp nhiều giao
    dịch thì tool tự hỏi lại. Gọi xong lượt kết thúc.

    Args:
        transaction: id giao dịch (từ search_transactions) hoặc nội dung giao dịch.
        amount: số tiền mới đúng nguyên văn người dùng nói ("300k", "1tr2"…).
        category: hạng mục mới (khoản chi: id/nhãn hạng mục; khoản thu: nguồn thu).
        date: ngày mới "YYYY-MM-DD".
        description: nội dung mới.
        account: "cash" | "bank" | "e_wallet".
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        _guard_role(deps)
        hit = await _find(deps, transaction, "sửa")
        if hit is None:
            return STOP_MESSAGE
        found, fp = hit
        name = str(found.get("description", ""))
        wanted: dict[str, Any] = {}
        if amount is not None:
            wanted["amount"] = parse_vnd(amount)
        if date is not None:
            wanted["date"] = parse_day(date, "date").isoformat()
        if description is not None:
            wanted["description"] = clean_text(description, MAX_TX_DESCRIPTION, "Nội dung", required=True)
        if account is not None:
            wanted["account"] = _account(account)
        if category is not None:
            if found.get("type") == "income":
                income = _income_category(deps, category)
                if income is None:
                    return STOP_MESSAGE
                wanted["category"] = income
            else:
                cat = await _expense_category(deps, category)
                if cat is None:
                    return STOP_MESSAGE
                wanted["category"] = cat[0]

        changes = {k: v for k, v in wanted.items() if found.get(k) != v}
        if not changes:
            raise ToolError(f'Giao dịch "{name}" đã đúng như vậy — không có thay đổi nào để đề xuất.')
        stage(deps, {"type": "finance.update", "txId": found["id"], "changes": changes, "base": {"fingerprint": fp}},
              target_key="txId", name=name)
        extra = f" (số tiền mới {money(changes['amount'])})" if "amount" in changes else ""
        return f'Đã ghi nhận đề xuất sửa giao dịch "{name}"{extra}. {PENDING}'


async def propose_delete_transaction(ctx: RunContext[AppDeps], transaction: str) -> str:
    """ĐỀ XUẤT xoá một giao dịch thu chi (kèm ảnh hoá đơn). KHÔNG ghi thật: người dùng phải bấm Duyệt.

    Gọi xong lượt kết thúc.

    Args:
        transaction: id giao dịch (từ search_transactions) hoặc nội dung; khớp nhiều giao dịch thì tool tự hỏi lại.
    """
    with flag_failures(ctx.deps):
        deps = ctx.deps
        _guard_role(deps)
        hit = await _find(deps, transaction, "xoá")
        if hit is None:
            return STOP_MESSAGE
        found, fp = hit
        name = str(found.get("description", ""))
        stage(deps, {"type": "finance.delete", "txId": found["id"], "base": {"fingerprint": fp}},
              target_key="txId", name=name)
        return f'Đã ghi nhận đề xuất xoá giao dịch "{name}" ({money(found.get("amount"))}). {PENDING}'


finance_toolset: FunctionToolset[AppDeps] = FunctionToolset([
    propose_create_transaction, propose_update_transaction, propose_delete_transaction,
])
