"""parse_vnd: cách người Việt viết tiền → số nguyên đồng. Nhập nhằng → ToolError (model hỏi lại), KHÔNG đoán."""

import pytest

from family_agent.harness.deps import ToolError
from family_agent.harness.money import MAX_AMOUNT, amount_question, parse_vnd, unitless_question


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


# --- số tiền phải có trong lời người dùng (eval phase 9: model tự thêm đơn vị cho "150", "1,5") ---


@pytest.mark.parametrize(("texts", "value", "options"), [
    (["Hôm nay đi chợ hết 150"], 150_000, ["150.000đ", "150.000.000đ"]),
    (["Ghi chi 1,5 tiền chợ hôm nay"], 1_500_000, ["1.500đ", "1.500.000đ"]),
    (["Ghi chi 1,5 tiền chợ hôm nay"], 1_500, ["1.500đ", "1.500.000đ"]),
])
def test_model_tu_them_don_vi_thi_hoi_lai(texts: list[str], value: int, options: list[str]) -> None:
    asked = amount_question(value, texts)
    assert asked is not None
    question, opts = asked
    assert "đơn vị" in question
    assert opts == options


@pytest.mark.parametrize(("texts", "value"), [
    ([], 150_000),  # không có lời người dùng (gọi tool trực tiếp) → không kiểm
    (["Hôm nay đi chợ hết 250k"], 250_000),
    (["Ghi khoản chi 1tr2 tiền học tiếng Anh"], 1_200_000),
    (["Bố được thưởng 2 triệu rưỡi"], 2_500_000),
    (["Tiền điện tháng 9 thực ra là 900 nghìn, sửa lại giúp mình"], 900_000),
    (["Chi 1,5 triệu mua quần áo"], 1_500_000),
    (["Trả 1.250.000đ tiền học"], 1_250_000),
    (["Giao Bin dọn phòng lúc 6 giờ và ghi chi 50k"], 50_000),
    (["Hôm nay đi chợ hết 150", "150 nghìn"], 150_000),  # trả lời câu hỏi lại ở tin nhắn sau
    (["Hôm nay đi chợ hết 150", "nghìn"], 150_000),
    (["Hôm nay đi chợ hết 150", "150.000đ"], 150_000),  # bấm lựa chọn
    (["chi năm trăm nghìn tiền nhà"], 500_000),  # chữ số viết bằng lời — không đoán được, không chặn
    (["Xoá khoản đổ xăng hôm 7/10 rồi ghi lại 80k"], 80_000),
])
def test_so_tien_nguoi_dung_da_noi_thi_cho_qua(texts: list[str], value: int) -> None:
    assert amount_question(value, texts) is None


def test_so_tien_bia_khi_nguoi_dung_khong_noi_so_nao() -> None:
    asked = amount_question(5_000_000, ["Ghi một khoản chi tiền nhà"])
    assert asked is not None and "bao nhiêu" in asked[0] and asked[1] == []


@pytest.mark.parametrize(("raw", "options"), [
    ("150", ["150.000đ", "150.000.000đ"]),
    (150, ["150.000đ", "150.000.000đ"]),
    ("1,5", ["1.500đ", "1.500.000đ"]),
    (" 2.5 ", ["2.500đ", "2.500.000đ"]),
])
def test_model_truyen_so_khong_don_vi_thi_hoi_lai(raw: object, options: list[str]) -> None:
    asked = unitless_question(raw)
    assert asked is not None and "đơn vị" in asked[0] and asked[1] == options


@pytest.mark.parametrize("raw", ["250k", "abc", "1tr25", "250000", 250000, "1.500k", True])
def test_khong_phai_so_tran_thi_khong_hoi(raw: object) -> None:
    assert unitless_question(raw) is None


# --- review: số dính ngày/tháng, thứ tự tin nhắn, hậu tố tiền tệ, nghìn cách khoảng trắng, số viết bằng chữ ----------

@pytest.mark.parametrize(("texts", "value"), [
    (["tiền điện tháng 9 150"], 150_000),  # H1: "150" không được bị "9" nuốt làm đuôi
    (["8/10 150"], 150_000),
    (["ngày 2 30"], 30_000),
    (["mua 2 150"], 150_000),
    (["lương 15tr", "ghi chi 15"], 15_000_000),  # M1: số cũ không xác nhận số trần mới
    (["tháng này tiêu mấy triệu rồi", "ghi chi đi chợ 150"], 150_000_000),
])
def test_review_van_hoi_lai(texts: list[str], value: int) -> None:
    assert amount_question(value, texts) is not None


@pytest.mark.parametrize(("texts", "value"), [
    (["chi 50kđ ăn sáng"], 50_000),  # M3: hậu tố tiền tệ sau đơn vị
    (["chi 2 000 000 tiền học"], 2_000_000),  # nghìn cách khoảng trắng
    (["đi chợ hết hai trăm k"], 200_000),  # số viết bằng chữ: không đoán được, không chặn
    (["mua rau trăm rưỡi"], 150_000),
])
def test_review_cho_qua(texts: list[str], value: int) -> None:
    assert amount_question(value, texts) is None


@pytest.mark.parametrize("texts", [["Ghi chi tiền điện ngày 8/10"], ["tiền điện tháng 9"], ["họp lúc 7h"]])
def test_review_ngay_thang_gio_khong_phai_so_tien(texts: list[str]) -> None:
    asked = amount_question(500_000, texts)  # M2: model bịa số tiền
    assert asked is not None and "bao nhiêu" in asked[0]
