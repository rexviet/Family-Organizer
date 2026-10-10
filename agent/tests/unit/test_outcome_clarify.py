"""OutcomeSlot (≤ 10 operation, không trùng, luôn hợp lệ theo hợp đồng) và ClarificationSink."""

import pytest

from family_agent.harness.clarify import MAX_ENTRIES, MAX_OPTIONS, ClarificationError, ClarificationSink
from family_agent.harness.outcome import OutcomeError, OutcomeSlot

H64 = "a" * 64


def add_op(*names: str) -> dict[str, object]:
    return {"type": "shopping.add", "items": [{"name": n} for n in names]}


def del_op(i: int) -> dict[str, object]:
    return {"type": "shopping.delete", "itemId": f"item_{i}", "base": {"updatedAt": "2026-10-01T00:00:00.000Z"}}


# --- OutcomeSlot -------------------------------------------------------------

def test_slot_moi_rong() -> None:
    slot = OutcomeSlot()
    assert slot.is_empty()
    assert slot.operations == []


def test_slot_them_op_hop_le() -> None:
    slot = OutcomeSlot()
    assert slot.add(add_op("Sữa")) is True
    assert not slot.is_empty()
    assert slot.operations == [add_op("Sữa")]


def test_slot_op_trung_khong_them_lan_hai() -> None:
    slot = OutcomeSlot()
    assert slot.add(add_op("Sữa")) is True
    assert slot.add(add_op("Sữa")) is False
    assert len(slot.operations) == 1


def test_slot_toi_da_10_op_vuot_thi_loi_tieng_viet() -> None:
    slot = OutcomeSlot()
    for i in range(10):
        slot.add(del_op(i))
    with pytest.raises(OutcomeError, match="tối đa 10"):
        slot.add(del_op(99))
    assert len(slot.operations) == 10


def test_slot_op_sai_hop_dong_bi_tu_choi_va_khong_ghi() -> None:
    slot = OutcomeSlot()
    with pytest.raises(OutcomeError):
        slot.add({"type": "shopping.add", "items": [{"name": ""}]})
    with pytest.raises(OutcomeError):
        slot.add({"type": "khong.co", "x": 1})
    assert slot.is_empty()


def test_slot_tong_mon_vuot_30_bi_tu_choi() -> None:
    slot = OutcomeSlot()
    slot.add(add_op(*[f"a{i}" for i in range(20)]))
    with pytest.raises(OutcomeError, match="30"):
        slot.add(add_op(*[f"b{i}" for i in range(11)]))
    assert len(slot.operations) == 1


def test_slot_op_dua_vao_bi_sao_chep() -> None:
    slot = OutcomeSlot()
    op = add_op("Sữa")
    slot.add(op)
    op["items"] = []  # sửa đầu vào gốc không làm hỏng slot
    assert slot.operations == [add_op("Sữa")]


# --- ClarificationSink -------------------------------------------------------

def test_sink_ghi_va_doc_cau_hoi_dau() -> None:
    sink = ClarificationSink()
    assert sink.first() is None
    sink.ask("Bạn muốn nói ai?", ["Lan", "Bà ngoại"])
    sink.ask("Câu hai?")
    first = sink.first()
    assert first is not None
    assert first.question == "Bạn muốn nói ai?"
    assert first.options == ("Lan", "Bà ngoại")


def test_sink_khong_trung_cau_hoi() -> None:
    sink = ClarificationSink()
    assert sink.ask("Ai?", ["A"]) is True
    assert sink.ask("Ai?", ["A"]) is False
    assert len(sink.entries) == 1


def test_sink_gioi_han_so_cau_va_so_lua_chon() -> None:
    sink = ClarificationSink()
    for i in range(MAX_ENTRIES + 5):
        sink.ask(f"Câu {i}?")
    assert len(sink.entries) == MAX_ENTRIES
    sink2 = ClarificationSink()
    sink2.ask("Chọn?", [str(i) for i in range(MAX_OPTIONS + 7)])
    first = sink2.first()
    assert first is not None
    assert len(first.options) == MAX_OPTIONS


def test_sink_chuan_hoa_va_tu_choi_cau_hoi_rong() -> None:
    sink = ClarificationSink()
    with pytest.raises(ClarificationError):
        sink.ask("   ")
    sink.ask("  Ai?  ", ["  A  ", "", "A"])
    first = sink.first()
    assert first is not None
    assert first.question == "Ai?"
    assert first.options == ("A",)  # bỏ rỗng, bỏ trùng, cắt khoảng trắng
