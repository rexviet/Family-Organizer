"""parse_vnd: cách người Việt viết tiền → số nguyên đồng. Nhập nhằng → ToolError (model hỏi lại), KHÔNG đoán."""

import pytest

from family_agent.harness.deps import ToolError
from family_agent.harness.money import MAX_AMOUNT, parse_vnd


@pytest.mark.parametrize(("text", "want"), [
    # số trần / có dấu phân cách nghìn
    ("250000", 250_000),
    ("250.000", 250_000),
    ("250,000", 250_000),
    ("1.250.000", 1_250_000),
    ("250.000đ", 250_000),
    ("250.000 đ", 250_000),
    ("250.000 VND", 250_000),
    ("250.000 vnđ", 250_000),
    ("50 nghìn đồng", 50_000),
    # k / nghìn / ngàn
    ("250k", 250_000),
    ("250K", 250_000),
    ("250 nghìn", 250_000),
    ("250 ngàn", 250_000),
    ("250 nghin", 250_000),
    ("2k5", 2_500),
    ("1,5k", 1_500),
    # triệu / tr / củ
    ("1tr2", 1_200_000),
    ("1tr250", 1_250_000),
    ("1 triệu 2", 1_200_000),
    ("1,5 triệu", 1_500_000),
    ("1.5tr", 1_500_000),
    ("2 triệu rưỡi", 2_500_000),
    ("3 củ", 3_000_000),
    ("1 triệu 200 nghìn", 1_200_000),
    ("1tr200k", 1_200_000),
    ("15 triệu", 15_000_000),
    # tỷ / lít (100 nghìn)
    ("1 tỷ 2", 1_200_000_000),
    ("2 tỉ", 2_000_000_000),
    ("3 lít", 300_000),
    ("nửa triệu", 500_000),
    ("  120K  ", 120_000),
    ("1 000 000", 1_000_000),
    ("1tr050", 1_050_000),
    ("2k500", 2_500),
])
def test_parse_cac_cach_viet(text: str, want: int) -> None:
    assert parse_vnd(text) == want


def test_so_nguyen_giu_nguyen() -> None:
    assert parse_vnd(250000) == 250_000


@pytest.mark.parametrize("bad", [
    "", "   ", "abc", "0", "0k", "-50k", "1,5",  # "1,5" không đơn vị: 1,5 đồng hay 1.500? → hỏi lại
    "1.500k",  # 1.500k = 1,5k hay 1500k? → hỏi lại
    "1.2345k",  # 1234,5 đồng — không phải số nguyên
    "200k 1tr",  # đơn vị không giảm dần
    "1tr2tr", "k", "250kk", "1e6", "10000 tỷ",
    True, 0, -1, 1.5, 2_000_000_000_000,
    # review H1: số trần < 1000 thường là "nghìn" bị nói tắt ("đi chợ hết 150") → hỏi lại
    "150", "999", 150, 999.0,
    # review H2/M1: đuôi 2 chữ số ("1tr50" = 1,5tr hay 1.050.000?) hoặc quá dài → hỏi lại
    "1tr25", "1 triệu 50", "2k50", "1tr 200k 50", "1tr2000000", "2k5000",
    # review H3: hai số tách bằng khoảng trắng không được dính vào nhau
    "10 20", "100 200k", "1tr 2 3",
])
def test_tu_choi(bad: object) -> None:
    with pytest.raises(ToolError):
        parse_vnd(bad)  # type: ignore[arg-type]


def test_so_thuc_nguyen_van_duoc_nhan() -> None:
    # Model đôi khi gửi 250000.0 (JSON không phân biệt) — đúng số nguyên thì nhận.
    assert parse_vnd(250000.0) == 250_000


def test_gioi_han_hop_dong() -> None:
    assert parse_vnd(MAX_AMOUNT) == MAX_AMOUNT
    with pytest.raises(ToolError):
        parse_vnd(MAX_AMOUNT + 1)
