"""OutcomeSlot — nơi duy nhất các tool `propose_*` ghi kết quả của lượt (spec §2.1).

Agent không bao giờ ghi dữ liệu thật; thứ duy nhất đi ra khỏi lượt là danh sách operation này,
và mỗi phần tử đã được kiểm bằng đúng validator của hợp đồng (contract.py) ngay lúc thêm vào.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from family_agent.contract import LIMITS, canonical, validate_operations

MAX_OPERATIONS: int = LIMITS["maxOperations"]


class OutcomeError(ValueError):
    """Thông điệp tiếng Việt — model nhìn thấy (qua lỗi tool) để tự sửa đề xuất."""


@dataclass
class OutcomeSlot:
    max_ops: int = MAX_OPERATIONS
    operations: list[dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.operations

    def add(self, op: dict[str, Any]) -> bool:
        """Thêm một operation. True = đã thêm; False = trùng hệt; ném OutcomeError nếu vượt giới hạn/sai hợp đồng."""
        try:
            key = canonical(op)
        except ValueError as e:
            raise OutcomeError(f"Đề xuất không hợp lệ: {e}") from None
        if any(canonical(existing) == key for existing in self.operations):
            return False
        if len(self.operations) >= self.max_ops:
            raise OutcomeError(f"Một lượt chỉ đề xuất tối đa {self.max_ops} thay đổi. Hãy chia nhỏ yêu cầu.")
        result = validate_operations([*self.operations, op])
        if not result.ok:
            first = result.errors[0]
            raise OutcomeError(f"Đề xuất không hợp lệ ({first.path}): {first.message}")
        # Dùng bản sao đã chuẩn hoá của validator — không giữ tham chiếu tới đầu vào của tool.
        self.operations = result.operations
        return True
