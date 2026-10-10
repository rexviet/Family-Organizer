"""3 tool đề xuất đi chợ + ask_user: validate, gộp trùng không dấu, id lạ → hỏi lại, base.updatedAt, giới hạn."""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
import respx

from family_agent.contract import validate_operations
from family_agent.harness.deps import AppApiError, AppDeps, ToolError, UserInfo, build_http_client
from family_agent.harness.tools import ask, shopping

pytestmark = pytest.mark.anyio

BASE = "http://app.test:3000"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def deps() -> AsyncIterator[AppDeps]:
    http = build_http_client(BASE, "tok-123")
    yield AppDeps(http=http, user=UserInfo("u_lan", "Mẹ Lan", "member"), today="2026-10-10", weekday="Thứ Bảy")
    await http.aclose()


def ctx(d: AppDeps) -> Any:
    return SimpleNamespace(deps=d)


def item(i: str, name: str, purchased: bool, updated: str) -> dict[str, Any]:
    return {"id": i, "name": name, "quantity": "", "isPurchased": purchased, "creatorId": "u", "createdAt": "x",
            "updatedAt": updated}


SHOP = {"shoppingItems": [
    item("s1", "Sữa tươi", False, "2026-10-01T00:00:00.000Z"),
    item("s2", "Gạo", True, "2026-10-02T00:00:00.000Z"),
    item("s3", "Dầu ăn", False, "2026-10-03T00:00:00.000Z"),
]}


def serve(payload: Any = SHOP, status: int = 200) -> respx.Route:
    return respx.get(f"{BASE}/api/shopping").respond(status, json=payload)


# --- propose_add_shopping_items ------------------------------------------------------

async def test_them_mon_ghi_op_hop_le(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await shopping.propose_add_shopping_items(
            ctx(deps), items=[{"name": "Sữa chua"}, {"name": "Trứng", "quantity": "2 chục", "note": "gà ta"}],
        )
    assert deps.outcome.operations == [{
        "type": "shopping.add",
        "items": [{"name": "Sữa chua"}, {"name": "Trứng", "quantity": "2 chục", "note": "gà ta"}],
    }]
    assert validate_operations(deps.outcome.operations).ok
    assert "chờ" in msg.lower() and "2" in msg  # nói rõ đây mới là đề xuất, chưa ghi


async def test_them_mon_nhan_chuoi_tro_tran(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_add_shopping_items(ctx(deps), items=["Cà chua", "  Rau   muống "])
    assert deps.outcome.operations[0]["items"] == [{"name": "Cà chua"}, {"name": "Rau muống"}]


async def test_gop_trung_ten_khong_dau_trong_cung_lan_goi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_add_shopping_items(
            ctx(deps), items=[{"name": "Rau muống"}, {"name": "rau MUONG", "quantity": "2 bó"}, "Đường"],
        )
    assert deps.outcome.operations[0]["items"] == [{"name": "Rau muống", "quantity": "2 bó"}, {"name": "Đường"}]


async def test_mon_da_co_trong_danh_sach_chua_mua_thi_bo_qua_va_bao(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await shopping.propose_add_shopping_items(ctx(deps), items=["sua tuoi", "Bột giặt"])
    assert deps.outcome.operations[0]["items"] == [{"name": "Bột giặt"}]
    assert "Sữa tươi" in msg and "đã có" in msg


async def test_tat_ca_mon_da_co_thi_khong_ghi_op(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await shopping.propose_add_shopping_items(ctx(deps), items=["Sữa tươi", "dầu ăn"])
    assert deps.outcome.is_empty()
    assert "không cần" in msg.lower() or "đã có" in msg


async def test_mon_da_mua_roi_van_them_duoc(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_add_shopping_items(ctx(deps), items=["Gạo"])
    assert deps.outcome.operations[0]["items"] == [{"name": "Gạo"}]


@pytest.mark.parametrize("items", [
    [], [""], ["   "], [{"name": ""}], ["x" * 101], [{"name": "Gạo", "quantity": "q" * 51}],
    [{"name": "Gạo", "note": "n" * 201}], [{"quantity": "1"}],
])
async def test_dau_vao_sai_la_loi_tieng_viet_va_khong_ghi_gi(deps: AppDeps, items: list[Any]) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError):
            await shopping.propose_add_shopping_items(ctx(deps), items=items)
    assert deps.outcome.is_empty()


async def test_hon_20_mon_tach_thanh_nhieu_op_va_toi_da_30(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_add_shopping_items(ctx(deps), items=[f"món {i}" for i in range(25)])
        assert [len(op["items"]) for op in deps.outcome.operations] == [20, 5]
        with pytest.raises(ToolError, match="30"):
            await shopping.propose_add_shopping_items(ctx(deps), items=[f"khác {i}" for i in range(6)])
    assert sum(len(op["items"]) for op in deps.outcome.operations) == 25


async def test_goi_lai_y_het_khong_nhan_doi(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_add_shopping_items(ctx(deps), items=["Cà chua"])
        await shopping.propose_add_shopping_items(ctx(deps), items=["Cà chua"])
    assert len(deps.outcome.operations) == 1


async def test_khong_doc_duoc_danh_sach_thi_khong_de_xuat(deps: AppDeps) -> None:
    with respx.mock:
        serve({"error": "x"}, status=500)
        with pytest.raises(AppApiError):
            await shopping.propose_add_shopping_items(ctx(deps), items=["Cà chua"])
    assert deps.outcome.is_empty()


# --- propose_set_purchased / propose_remove_shopping_items ----------------------------

async def test_danh_dau_da_mua_ghi_base_updated_at(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_set_purchased(ctx(deps), item_ids=["s1", "s3"], purchased=True)
    assert deps.outcome.operations == [
        {"type": "shopping.set_purchased", "itemId": "s1", "purchased": True,
         "base": {"updatedAt": "2026-10-01T00:00:00.000Z"}},
        {"type": "shopping.set_purchased", "itemId": "s3", "purchased": True,
         "base": {"updatedAt": "2026-10-03T00:00:00.000Z"}},
    ]
    assert validate_operations(deps.outcome.operations).ok


async def test_bo_danh_dau_dat_gia_tri_khong_lat(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_set_purchased(ctx(deps), item_ids=["s2"], purchased=False)
    assert deps.outcome.operations[0]["purchased"] is False


async def test_mon_da_o_dung_trang_thai_thi_bo_qua(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await shopping.propose_set_purchased(ctx(deps), item_ids=["s2", "s1", "s1"], purchased=True)
    assert [op["itemId"] for op in deps.outcome.operations] == ["s1"]  # s2 đã mua sẵn, s1 trùng id → 1 op
    assert "Gạo" in msg


async def test_id_la_thi_hoi_lai_khong_bia_op(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        msg = await shopping.propose_set_purchased(ctx(deps), item_ids=["s1", "s999"], purchased=True)
    assert deps.outcome.is_empty()  # nguyên cả lần gọi, không ghi một nửa
    first = deps.clarifications.first()
    assert first is not None
    assert "s999" not in first.question  # id nội bộ không hiện cho người dùng
    assert first.options == ("Sữa tươi", "Dầu ăn")  # gợi ý các món chưa mua
    assert "dừng" in msg.lower()


async def test_xoa_mon(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_remove_shopping_items(ctx(deps), item_ids=["s2"])
    assert deps.outcome.operations == [
        {"type": "shopping.delete", "itemId": "s2", "base": {"updatedAt": "2026-10-02T00:00:00.000Z"}},
    ]
    assert validate_operations(deps.outcome.operations).ok


async def test_xoa_id_la_hoi_lai_voi_moi_mon(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_remove_shopping_items(ctx(deps), item_ids=["nope"])
    first = deps.clarifications.first()
    assert first is not None and first.options == ("Sữa tươi", "Gạo", "Dầu ăn")
    assert deps.outcome.is_empty()


@pytest.mark.parametrize("ids", [[], [""], ["   "]])
async def test_khong_co_id_la_loi(deps: AppDeps, ids: list[str]) -> None:
    with respx.mock:
        serve()
        with pytest.raises(ToolError):
            await shopping.propose_remove_shopping_items(ctx(deps), item_ids=ids)
        with pytest.raises(ToolError):
            await shopping.propose_set_purchased(ctx(deps), item_ids=ids, purchased=True)


async def test_vuot_10_op_bao_loi(deps: AppDeps) -> None:
    many = {"shoppingItems": [item(f"i{n}", f"Món {n}", False, "2026-10-01T00:00:00.000Z") for n in range(12)]}
    with respx.mock:
        serve(many)
        with pytest.raises(ToolError, match="tối đa 10"):
            await shopping.propose_remove_shopping_items(ctx(deps), item_ids=[f"i{n}" for n in range(12)])


async def test_mon_thieu_updated_at_khong_de_xuat_duoc(deps: AppDeps) -> None:
    bad = {"shoppingItems": [{"id": "s1", "name": "Sữa", "isPurchased": False}]}
    with respx.mock:
        serve(bad)
        with pytest.raises(ToolError):
            await shopping.propose_remove_shopping_items(ctx(deps), item_ids=["s1"])


# --- ask_user ------------------------------------------------------------------------------

async def test_ask_user_ghi_vao_sink(deps: AppDeps) -> None:
    msg = await ask.ask_user(ctx(deps), question="Bạn nói 'mẹ' là Lan hay bà ngoại?", options=["Lan", "Bà ngoại"])
    first = deps.clarifications.first()
    assert first is not None and first.options == ("Lan", "Bà ngoại")
    assert "dừng" in msg.lower()


async def test_ask_user_cau_hoi_rong_la_loi(deps: AppDeps) -> None:
    with pytest.raises(ToolError):
        await ask.ask_user(ctx(deps), question="  ")


# --- review M2: xung đột trong cùng lượt -------------------------------------------------------------------------

async def test_khong_de_xuat_hai_thay_doi_cho_cung_mot_mon(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_set_purchased(ctx(deps), item_ids=["s1"], purchased=True)
        with pytest.raises(ToolError, match="Sữa tươi"):
            await shopping.propose_remove_shopping_items(ctx(deps), item_ids=["s1"])
        with pytest.raises(ToolError):
            await shopping.propose_set_purchased(ctx(deps), item_ids=["s3", "s1"], purchased=False)
    assert [op["itemId"] for op in deps.outcome.operations] == ["s1"]  # lần gọi lỗi không ghi gì


async def test_goi_lai_dung_thay_doi_cu_khong_phai_xung_dot(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_set_purchased(ctx(deps), item_ids=["s1"], purchased=True)
        await shopping.propose_set_purchased(ctx(deps), item_ids=["s1"], purchased=True)
    assert len(deps.outcome.operations) == 1


async def test_them_mon_bo_ten_da_de_xuat_trong_luot(deps: AppDeps) -> None:
    with respx.mock:
        serve()
        await shopping.propose_add_shopping_items(ctx(deps), items=["Trứng", "Hành"])
        msg = await shopping.propose_add_shopping_items(ctx(deps), items=["trung", "Tỏi"])
    assert deps.outcome.operations[1]["items"] == [{"name": "Tỏi"}]
    assert "Trứng".lower() in msg.lower() or "trung" in msg.lower()
    assert "lượt này" in msg
