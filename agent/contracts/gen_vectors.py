"""Tính lại hash trong vectors.json bằng cài đặt Python độc lập (chỉ dùng stdlib).

Chạy:  python3 agent/contracts/gen_vectors.py          # ghi lại canonical/planHash/fingerprint
       python3 agent/contracts/gen_vectors.py --check  # chỉ kiểm, lệch thì exit 1

Đây là bản cài "tham chiếu" phía Python, cố ý viết khác cách với server/agentContract.ts
(dùng json.dumps thay vì tự nối chuỗi) để hai bên đối chiếu nhau qua cùng bộ vector.
"""

import hashlib
import json
import sys
from pathlib import Path

VECTORS = Path(__file__).with_name("vectors.json")

FINGERPRINT_FIELDS = {
    "transaction": ["amount", "category", "date", "description", "account", "type"],
    "plan": [
        "title", "description", "startDate", "endDate", "isShared",
        "isRecurring", "recurrenceType", "recurrenceWeekdays", "color",
    ],
}

MAX_SAFE_INT = 2**53 - 1


def _check(value, path="$"):
    """Chỉ cho phép kiểu JSON mà hợp đồng dùng; số phải là số nguyên an toàn."""
    if value is None or isinstance(value, (bool, str)):
        if isinstance(value, str):
            value.encode("utf-8")  # chuỗi có surrogate lẻ -> UnicodeEncodeError
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INT:
            raise ValueError(f"{path}: số nguyên vượt 2^53-1")
        return
    if isinstance(value, float):
        raise ValueError(f"{path}: không chấp nhận số thực")
    if isinstance(value, list):
        for i, v in enumerate(value):
            _check(v, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{path}: key phải là chuỗi")
            k.encode("utf-8")  # key có surrogate lẻ -> UnicodeEncodeError
            _check(v, f"{path}.{k}")
        return
    raise ValueError(f"{path}: kiểu không hỗ trợ {type(value).__name__}")


def canonical(value) -> str:
    _check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_hash(operations) -> str:
    return sha256hex(canonical(operations))


def fingerprint(kind: str, record: dict) -> str:
    picked = {f: record.get(f) for f in FINGERPRINT_FIELDS[kind]}
    return sha256hex(canonical(picked))


def main() -> int:
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    for v in data["canonical"]:
        v["canonical"] = canonical(v["value"])
    for v in data["planHash"]:
        v["canonical"] = canonical(v["operations"])
        v["planHash"] = plan_hash(v["operations"])
    for v in data["fingerprint"]:
        v["fingerprint"] = fingerprint(v["kind"], v["record"])
    out = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        if out != VECTORS.read_text(encoding="utf-8"):
            print("vectors.json lệch với cài đặt Python", file=sys.stderr)
            return 1
        print("vectors.json khớp")
        return 0
    VECTORS.write_text(out, encoding="utf-8")
    print(f"đã ghi {VECTORS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
