"""Từ vựng dùng chung: nhãn quan hệ, hạng mục chi mặc định, so khớp không dấu."""

from __future__ import annotations

import unicodedata
from typing import Final

# Khớp FAMILY_RELATION_LABELS (src/types.ts).
RELATION_LABELS: Final = {
    "ong_noi": "Ông nội", "ba_noi": "Bà nội", "ong_ngoai": "Ông ngoại", "ba_ngoai": "Bà ngoại",
    "ba": "Ba", "me": "Mẹ", "con": "Con", "anh_chi_em": "Anh/Chị/Em", "khach": "Khách", "khac": "Khác",
}

# Hạng mục CHI mặc định (src/utils/expenseCategories.ts + nhãn vi.json) — id lưu trong transaction.category.
BUILTIN_CATEGORIES: Final = {
    "food": "Ăn uống", "education2": "Học tập", "utilities": "Điện nước", "shopping": "Mua sắm",
    "medical": "Y tế", "transport": "Đi lại", "debt_bank": "Trả nợ ngân hàng", "debt_personal": "Trả nợ cá nhân",
    "funeral": "Ma chay", "ceremony": "Hiếu hỉ", "other": "Khoản khác",
}


def fold(s: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (đ → d), gộp khoảng trắng — để tìm "tien dien" khớp "Tiền điện"."""
    decomposed = unicodedata.normalize("NFD", s.casefold().replace("đ", "d"))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())

# Nguồn THU gợi ý (INCOME_CATEGORIES ở src/components/Finance.tsx) — hạng mục thu là chữ tự do, lưu nguyên văn.
INCOME_CATEGORIES: Final = (
    "Lương tháng", "Tiền thưởng", "Làm thêm / Freelance", "Hoa hồng bán hàng", "Cổ tức",
    "Lợi nhuận cổ phần / Đầu tư", "Cho thuê (nhà/xe...)", "Tiền mượn / Vay", "Được cho / Biếu tặng",
)
