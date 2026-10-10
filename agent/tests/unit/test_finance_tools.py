"""3 tool đề xuất Thu chi (phase 9): số tiền parse bằng code, hạng mục chi phải có thật (cả hạng mục tự thêm),
không rõ → hỏi lại; base = fingerprint bản ghi gốc (số tiền lẻ → không đề xuất); chỉ Admin/Thành viên."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
import respx

from family_agent.contract import fingerprint, validate_operations
from family_agent.harness.deps import AppDeps, Member, ToolError, UserInfo, build_http_client
from family_agent.harness.tools import finance
from family_agent.harness.tools.ask import STOP_MESSAGE

pytestmark = pytest.mark.anyio

BASE = "http://app.test:3000"
U0 = "2026-10-01T00:00:00.000Z"
MEMBERS = [
    Member(id="u_lan", fullName="Mẹ Lan", role="member", relation="Mẹ"),
    Member(id="u_admin", fullName="Ba Hùng", role="admin", relation="Ba"),
    Member(id="u_bin", fullName="Bin", role="child", relation="Con"),
]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_deps(user: UserInfo) -> AppDeps:
    return AppDeps(
        http=build_http_client(BASE, "tok"), user=user, today="2026-10-10", weekday="Thứ Bảy", members=list(MEMBERS),
    )


@pytest.fixture
async def deps() -> AsyncIterator[AppDeps]:
    d = make_deps(UserInfo("u_lan", "Mẹ Lan", "member"))
    yield d
    await d.http.aclose()


def ctx(d: AppDeps) -> Any:
    return SimpleNamespace(deps=d)


def tx(i: str, description: str, **kw: Any) -> dict[str, Any]:
    row = {"id": i, "type": "expense", "amount": 250000, "category": "food", "account": "cash",
           "description": description, "date": "2026-10-08", "creatorId": "u_lan", "createdAt": U0,
           "receiptImage": "/uploads/receipts/r1.jpg"}
    row.update(kw)
    return row


TXS = [
    tx("x1", "Đi chợ"),
    tx("x2", "Tiền điện tháng 9", amount=850000, category="utilities", account="bank"),
    tx("x3", "Lương tháng 9", type="income", amount=15000000, category="Lương tháng", account="bank"),
    tx("x4", "Ăn phở", date="2026-10-09"),
    tx("x5", "Ăn phở", date="2026-08-01"),
    tx("x6", "Ăn phở", date="2026-10-05", amount=120000),
    tx("x_frac", "Cà phê", amount=35000.5),
    tx("x_pet", "Thức ăn cho mèo", category="cc_pet"),
]
CATS = {"customCategories": [{"id": "cc_pet", "label": "Thú cưng", "emoji": "🐶", "color": "teal"}],
        "hiddenBuiltinCategories": ["funeral"]}


def serve() -> None:
    respx.get(f"{BASE}/api/finance").respond(200, json={"transactions": TXS})
    respx.get(f"{BASE}/api/finance/categories").respond(200, json=CATS)


def ops(d: AppDeps) -> list[dict[str, Any]]:
    assert validate_operations(d.outcome.operations).ok
    return d.outcome.operations


# --- finance.create ---------------------------------------------------------------------------------------------------

async def test_ghi_khoan_chi_parse_tien(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await finance.propose_create_transaction(
            ctx(deps), tx_type="expense", amount="250k", category="food", description="Đi chợ sáng",
        )
    assert ops(deps) == [{"type": "finance.create", "txType": "expense", "amount": 250000, "category": "food",
                          "date": "2026-10-10", "description": "Đi chợ sáng"}]
    assert "250.000" in msg  # model thấy số tiền đã đổi để đối chiếu
    assert "chờ" in msg.lower()


async def test_hang_muc_theo_nhan_va_tu_them(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_create_transaction(
            ctx(deps), tx_type="expense", amount="1tr2", category="Thú cưng", description="Tiêm phòng",
            date="2026-10-09", account="bank",
        )
    assert ops(deps) == [{"type": "finance.create", "txType": "expense", "amount": 1200000, "category": "cc_pet",
                          "date": "2026-10-09", "description": "Tiêm phòng", "account": "bank"}]


async def test_nhan_hang_muc_mac_dinh_khong_dau(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_create_transaction(ctx(deps), tx_type="expense", amount=50000, category="an uong",
                                                 description="Bún")
    assert ops(deps)[0]["category"] == "food"


async def test_mo_ta_trong_lay_nhan_hang_muc(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_create_transaction(ctx(deps), tx_type="expense", amount="850k", category="utilities")
    assert ops(deps)[0]["description"] == "Điện nước"


@pytest.mark.parametrize("cat", ["", "tiền lì xì lung tung", "funeral"])  # rỗng / không có / mặc định đã ẩn
async def test_hang_muc_chi_khong_ro_thi_hoi_lai(deps: AppDeps, cat: str) -> None:
    with respx.mock:
        serve()
        msg = await finance.propose_create_transaction(ctx(deps), tx_type="expense", amount="100k", category=cat,
                                                       description="x")
    assert msg == STOP_MESSAGE
    assert deps.outcome.is_empty()
    asked = deps.clarifications.first()
    assert asked is not None and "hạng mục" in asked.question
    assert "Ăn uống" in asked.options and "Thú cưng" in asked.options and "Ma chay" not in asked.options
    assert len(asked.options) <= 10


async def test_khoan_thu_hang_muc_tu_do(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_create_transaction(ctx(deps), tx_type="income", amount="15 triệu", category="Lương tháng",
                                                 description="Lương tháng 10")
    assert ops(deps)[0] == {"type": "finance.create", "txType": "income", "amount": 15000000,
                            "category": "Lương tháng", "date": "2026-10-10", "description": "Lương tháng 10"}


async def test_khoan_thu_thieu_nguon_thi_hoi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await finance.propose_create_transaction(ctx(deps), tx_type="income", amount="2tr", category=" ")
    assert msg == STOP_MESSAGE
    asked = deps.clarifications.first()
    assert asked is not None and "Lương tháng" in asked.options


@pytest.mark.parametrize("kw", [
    {"tx_type": "chi", "amount": "1k", "category": "food"},
    {"tx_type": "expense", "amount": 0, "category": "food"},
    {"tx_type": "expense", "amount": "1k", "category": "food", "date": "10/10/2026"},
    {"tx_type": "expense", "amount": "1k", "category": "food", "date": "2026-02-30"},
    {"tx_type": "expense", "amount": "1k", "category": "food", "account": "visa"},
    {"tx_type": "expense", "amount": "1k", "category": "food", "description": "x" * 501},
    {"tx_type": "income", "amount": "1k", "category": "y" * 101},
])
async def test_tao_tham_so_sai(deps: AppDeps, kw: dict[str, Any]) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError):
            await finance.propose_create_transaction(ctx(deps), **kw)
    assert deps.outcome.is_empty()


# --- số tiền không đơn vị / model tự gắn đơn vị → hỏi lại kèm lựa chọn (eval phase 9 A08, A09) ----------------------

@pytest.mark.parametrize(("said", "amount", "options"), [
    ("Hôm nay đi chợ hết 150", "150k", ["150.000đ", "150.000.000đ"]),  # model tự thêm "k"
    ("Hôm nay đi chợ hết 150", 150000, ["150.000đ", "150.000.000đ"]),
    ("Ghi chi 1,5 tiền chợ hôm nay", "1,5 triệu", ["1.500đ", "1.500.000đ"]),
    ("Ghi chi 1,5 tiền chợ hôm nay", "1,5", ["1.500đ", "1.500.000đ"]),  # model truyền nguyên văn
    ("", "150", ["150.000đ", "150.000.000đ"]),  # không có lời người dùng: số trần vẫn hỏi lại
])
async def test_so_tien_khong_don_vi_thi_hoi_lai(deps: AppDeps, said: str, amount: Any, options: list[str]) -> None:
    deps.user_texts = [said] if said else []
    with respx.mock:
        serve()
        msg = await finance.propose_create_transaction(ctx(deps), tx_type="expense", amount=amount, category="food")
    assert msg == STOP_MESSAGE
    assert deps.outcome.is_empty()
    asked = deps.clarifications.first()
    assert asked is not None and "đơn vị" in asked.question and list(asked.options) == options


async def test_so_tien_bia_thi_hoi_so_tien(deps: AppDeps) -> None:
    deps.user_texts = ["Ghi một khoản chi tiền nhà"]
    with respx.mock:
        serve()
        msg = await finance.propose_create_transaction(ctx(deps), tx_type="expense", amount="5tr", category="other")
    assert msg == STOP_MESSAGE and deps.outcome.is_empty()
    asked = deps.clarifications.first()
    assert asked is not None and "bao nhiêu" in asked.question


async def test_so_tien_nguoi_dung_noi_ro_thi_de_xuat(deps: AppDeps) -> None:
    deps.user_texts = ["Hôm nay đi chợ hết 150", "150 nghìn"]
    with respx.mock:
        serve()
        await finance.propose_create_transaction(ctx(deps), tx_type="expense", amount="150 nghìn", category="food")
    assert ops(deps)[0]["amount"] == 150000


async def test_sua_so_tien_khong_don_vi_thi_hoi_lai(deps: AppDeps) -> None:
    deps.user_texts = ["Sửa tiền điện tháng 9 thành 900"]
    with respx.mock:
        serve()
        msg = await finance.propose_update_transaction(ctx(deps), transaction="x2", amount="900k")
    assert msg == STOP_MESSAGE and deps.outcome.is_empty()
    asked = deps.clarifications.first()
    assert asked is not None and list(asked.options) == ["900.000đ", "900.000.000đ"]


@pytest.mark.parametrize("role", ["child", "guest"])
async def test_con_khach_khong_de_xuat_thu_chi(role: str) -> None:
    d = make_deps(UserInfo("u_bin", "Bin", role))
    try:
        with respx.mock:  # không request nào được gửi: chặn sớm
            for call in (
                finance.propose_create_transaction(ctx(d), tx_type="expense", amount="1k", category="food"),
                finance.propose_update_transaction(ctx(d), transaction="x1", amount="2k"),
                finance.propose_delete_transaction(ctx(d), transaction="x1"),
            ):
                with pytest.raises(ToolError, match="Admin/Thành viên"):
                    await call
        assert d.outcome.is_empty()
    finally:
        await d.http.aclose()


# --- finance.update ---------------------------------------------------------------------------------------------------

async def test_sua_so_tien_base_fingerprint(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await finance.propose_update_transaction(ctx(deps), transaction="x2", amount="900k")
    assert ops(deps) == [{"type": "finance.update", "txId": "x2", "changes": {"amount": 900000},
                          "base": {"fingerprint": fingerprint("transaction", TXS[1])}}]
    assert "900.000" in msg


async def test_sua_theo_mo_ta_va_chi_giu_truong_doi_that(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_update_transaction(ctx(deps), transaction="tiền điện", amount="850.000",
                                                 date="2026-10-01", account="bank")
    assert ops(deps)[0]["changes"] == {"date": "2026-10-01"}


async def test_sua_khong_doi_gi_thi_tu_choi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="không có thay đổi"):
            await finance.propose_update_transaction(ctx(deps), transaction="x1", amount="250k")


async def test_sua_hang_muc_theo_loai_giao_dich(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_update_transaction(ctx(deps), transaction="x1", category="Thú cưng")
        await finance.propose_update_transaction(ctx(deps), transaction="x3", category="Tiền thưởng")
    assert [o["changes"] for o in ops(deps)] == [{"category": "cc_pet"}, {"category": "Tiền thưởng"}]


async def test_ten_mo_ho_hoi_lai_uu_tien_gan_day(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await finance.propose_update_transaction(ctx(deps), transaction="Ăn phở", amount="100k")
    assert msg == STOP_MESSAGE
    asked = deps.clarifications.first()
    assert asked is not None
    # x5 (08/2026) cũ hơn 31 ngày → không nằm trong lựa chọn khi đã có bản ghi gần đây
    assert asked.options == ("Ăn phở — 250.000₫ — 09/10", "Ăn phở — 120.000₫ — 05/10")


async def test_chon_lai_bang_nhan(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_update_transaction(ctx(deps), transaction="Ăn phở — 120.000₫ — 05/10", amount="100k")
    assert ops(deps)[0]["txId"] == "x6"


async def test_so_tien_le_khong_de_xuat_duoc(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="sửa trực tiếp"):
            await finance.propose_update_transaction(ctx(deps), transaction="x_frac", amount="40k")
        with pytest.raises(ToolError, match="sửa trực tiếp"):
            await finance.propose_delete_transaction(ctx(deps), transaction="x_frac")


async def test_khong_tim_thay(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError, match="Không tìm thấy"):
            await finance.propose_update_transaction(ctx(deps), transaction="du lịch Đà Lạt", amount="1k")


# --- finance.delete ---------------------------------------------------------------------------------------------------

async def test_xoa(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await finance.propose_delete_transaction(ctx(deps), transaction="Lương tháng 9")
    assert ops(deps) == [{"type": "finance.delete", "txId": "x3",
                          "base": {"fingerprint": fingerprint("transaction", TXS[2])}}]
    assert "xoá" in msg


async def test_mot_giao_dich_chi_mot_thay_doi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await finance.propose_update_transaction(ctx(deps), transaction="x1", amount="300k")
        with pytest.raises(ToolError, match="đã có một đề xuất khác"):
            await finance.propose_delete_transaction(ctx(deps), transaction="x1")
