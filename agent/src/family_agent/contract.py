"""Hợp đồng operation Node ↔ Agent — bản cài phía Python.

Nguồn chân lý: agent/contracts/operations.schema.json (+ README.md cùng thư mục).
Bản Node: server/agentContract.ts. Hai bên phải ra cùng chuỗi trên agent/contracts/vectors.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal

# src/family_agent/contract.py → agent/contracts (repo) hoặc /app/contracts (image).
CONTRACTS_DIR = Path(os.environ.get("AGENT_CONTRACTS_DIR") or Path(__file__).resolve().parents[2] / "contracts")

SCHEMA: dict[str, Any] = json.loads((CONTRACTS_DIR / "operations.schema.json").read_text(encoding="utf-8"))
CONTRACT_VERSION: int = SCHEMA["contractVersion"]
LIMITS: dict[str, int] = SCHEMA["limits"]

MAX_SAFE_INT = 2**53 - 1
MAX_ERRORS = 50

# ---------------------------------------------------------------------------
# Canonical JSON + hash
# ---------------------------------------------------------------------------


def _check(value: object, path: str) -> None:
    """Chỉ cho phép kiểu JSON mà hợp đồng dùng; số phải là số nguyên an toàn (bool không tính là số)."""
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        _check_str(value, path)
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
            _check_str(k, path)
            _check(v, f"{path}.{k}")
        return
    raise ValueError(f"{path}: kiểu không hỗ trợ ({type(value).__name__})")


def _check_str(s: str, path: str) -> None:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"{path}: chuỗi có surrogate lẻ") from None


def canonical(value: object) -> str:
    """JSON chuẩn hoá: key sắp theo code point, không khoảng trắng, chỉ số nguyên. Ném ValueError nếu vi phạm."""
    _check(value, "$")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_hash(operations: object) -> str:
    """planHash = sha256hex(canonical(operations)) — thứ tự operation có nghĩa."""
    return _sha256hex(canonical(operations))


FingerprintKind = Literal["transaction", "plan"]

FINGERPRINT_FIELDS: dict[str, tuple[str, ...]] = {
    "transaction": ("amount", "category", "date", "description", "account", "type"),
    "plan": (
        "title", "description", "startDate", "endDate", "isShared",
        "isRecurring", "recurrenceType", "recurrenceWeekdays", "color",
    ),
}


def fingerprint(kind: FingerprintKind, record: dict[str, Any]) -> str:
    """Dấu vân tay cho bản ghi không có `updatedAt`; trường thiếu tính là null, trường ngoài FIELDS bỏ qua."""
    fields = FINGERPRINT_FIELDS.get(kind)
    if fields is None:
        raise ValueError(f"loại bản ghi không hỗ trợ: {kind}")
    return _sha256hex(canonical({f: record.get(f) for f in fields}))


# ---------------------------------------------------------------------------
# Validator — bộ con JSON Schema 2020-12 mà operations.schema.json dùng
# ---------------------------------------------------------------------------

_ANNOTATIONS = {"$schema", "$id", "$defs", "title", "description", "contractVersion", "limits"}
_KEYWORDS = {
    "$ref", "type", "const", "enum", "pattern", "minLength", "maxLength", "minimum", "maximum",
    "minItems", "maxItems", "uniqueItems", "items", "properties", "required",
    "additionalProperties", "minProperties", "oneOf",
}


@dataclass(frozen=True)
class ContractError:
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    # Bản sao dựng lại từ canonical JSON — lưu/hash/gửi đúng bản này, không dùng lại đầu vào gốc.
    operations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ContractError] = field(default_factory=list)


def _resolve_ref(ref: str) -> dict[str, Any]:
    prefix = "#/$defs/"
    defs: dict[str, Any] = SCHEMA.get("$defs", {})
    sub = defs.get(ref[len(prefix):]) if ref.startswith(prefix) else None
    if sub is None:
        raise ValueError(f"schema: không tìm thấy {ref}")
    return dict(sub)


def _assert_supported(s: dict[str, Any], at: str) -> None:
    """Chặn schema dùng từ khoá validator này không hiểu (nếu không sẽ bị bỏ qua âm thầm)."""
    for k, v in s.items():
        if k in _ANNOTATIONS:
            continue
        if k not in _KEYWORDS:
            raise ValueError(f'schema {at}: từ khoá chưa hỗ trợ "{k}"')
        if k == "additionalProperties" and v is not False:
            raise ValueError(f"schema {at}: additionalProperties chỉ hỗ trợ false")
        # fullmatch chỉ tương đương RegExp.test (Node) khi pattern neo cả hai đầu.
        if k == "pattern" and not (v.startswith("^") and v.endswith("$")):
            raise ValueError(f"schema {at}: pattern phải có ^…$")
    if "$ref" in s:
        _resolve_ref(s["$ref"])
    if "items" in s:
        _assert_supported(s["items"], f"{at}/items")
    for k, sub in s.get("properties", {}).items():
        _assert_supported(sub, f"{at}/properties/{k}")
    for i, sub in enumerate(s.get("oneOf", [])):
        _assert_supported(sub, f"{at}/oneOf/{i}")


_assert_supported(SCHEMA, "#")
for _name, _def in SCHEMA.get("$defs", {}).items():
    _assert_supported(_def, f"#/$defs/{_name}")


def _type_of(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer" if abs(v) <= MAX_SAFE_INT else "number"
    if isinstance(v, float):
        return "number"  # kể cả 1.0 — README: số phải là int thật
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object" if all(isinstance(k, str) for k in v) else "other"
    return "other"


def _same_json(a: object, b: object) -> bool:
    try:
        return canonical(a) == canonical(b)
    except ValueError:
        return False


@cache
def _regex(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _check_schema(s: dict[str, Any], v: object, path: str, out: list[ContractError]) -> None:
    if len(out) >= MAX_ERRORS:
        return
    if "$ref" in s:
        _check_schema(_resolve_ref(s["$ref"]), v, path, out)
        return

    if "type" in s:
        allowed = s["type"] if isinstance(s["type"], list) else [s["type"]]
        t = _type_of(v)
        if t not in allowed:
            out.append(ContractError(path, f"phải là {'|'.join(allowed)}, nhận {t}"))
            return
    if "const" in s and not _same_json(v, s["const"]):
        out.append(ContractError(path, f"phải bằng {json.dumps(s['const'], ensure_ascii=False)}"))
    if "enum" in s and not any(_same_json(v, e) for e in s["enum"]):
        out.append(ContractError(path, f"phải là một trong {', '.join(map(str, s['enum']))}"))

    if isinstance(v, str):
        n = len(v)  # Python đếm theo code point — đúng như JSON Schema
        if "minLength" in s and n < s["minLength"]:
            out.append(ContractError(path, f"ít nhất {s['minLength']} ký tự"))
        if "maxLength" in s and n > s["maxLength"]:
            out.append(ContractError(path, f"tối đa {s['maxLength']} ký tự"))
            return
        # fullmatch, không dùng search: `$` của re khớp cả trước "\n" cuối chuỗi.
        if "pattern" in s and not _regex(s["pattern"]).fullmatch(v):
            out.append(ContractError(path, f"sai định dạng ({s['pattern']})"))

    if isinstance(v, int | float) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            out.append(ContractError(path, f"phải ≥ {s['minimum']}"))
        if "maximum" in s and v > s["maximum"]:
            out.append(ContractError(path, f"phải ≤ {s['maximum']}"))

    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            out.append(ContractError(path, f"ít nhất {s['minItems']} phần tử"))
        if "maxItems" in s and len(v) > s["maxItems"]:
            out.append(ContractError(path, f"tối đa {s['maxItems']} phần tử"))
            return
        if s.get("uniqueItems") and any(
            any(_same_json(x, y) for y in v[:i]) for i, x in enumerate(v)
        ):
            out.append(ContractError(path, "phần tử bị trùng"))
        if "items" in s:
            for i, x in enumerate(v):
                _check_schema(s["items"], x, f"{path}[{i}]", out)

    if isinstance(v, dict) and _type_of(v) == "object":
        props: dict[str, Any] = s.get("properties", {})
        for k in s.get("required", []):
            if k not in v:
                out.append(ContractError(f"{path}.{k}", "thiếu trường bắt buộc"))
        if "minProperties" in s and len(v) < s["minProperties"]:
            out.append(ContractError(path, f"cần ít nhất {s['minProperties']} trường"))
        for k, x in v.items():
            if k in props:
                _check_schema(props[k], x, f"{path}.{k}", out)
            elif s.get("additionalProperties") is False:
                out.append(ContractError(f"{path}.{k}", "trường không được phép"))

    if "oneOf" in s:
        _check_one_of(s["oneOf"], v, path, out)


def _check_one_of(branches: list[dict[str, Any]], v: object, path: str, out: list[ContractError]) -> None:
    """Union phân biệt bằng `type`: chọn đúng nhánh theo const; không có `type` chuỗi thì theo luật oneOf chuẩn."""
    resolved = [_resolve_ref(b["$ref"]) if "$ref" in b else b for b in branches]
    if isinstance(v, dict) and isinstance(v.get("type"), str):
        for b in resolved:
            if b.get("properties", {}).get("type", {}).get("const") == v["type"]:
                _check_schema(b, v, path, out)
                return
        out.append(ContractError(f"{path}.type", f"operation không hỗ trợ: {v['type']}"))
        return
    matches = 0
    for b in resolved:
        errs: list[ContractError] = []
        _check_schema(b, v, path, errs)
        matches += not errs
    if matches != 1:
        out.append(ContractError(path, "không khớp đúng một loại operation"))


def validate_operations(data: object) -> ValidationResult:
    """Kiểm danh sách operation theo schema + giới hạn ngoài schema. Mọi thứ ngoài hợp đồng bị từ chối."""
    errors: list[ContractError] = []
    _check_schema(SCHEMA, data, "$", errors)
    ops: list[dict[str, Any]] = []
    if not errors:
        try:
            ops = json.loads(canonical(data))
        except ValueError as e:  # vd. surrogate lẻ
            errors.append(ContractError("$", str(e)))
    if not errors:
        total = sum(len(op["items"]) for op in ops if op["type"] == "shopping.add")
        if total > LIMITS["maxShoppingAddItemsTotal"]:
            errors.append(ContractError(
                "$", f"tổng số món đi chợ tối đa {LIMITS['maxShoppingAddItemsTotal']}, nhận {total}",
            ))
    if errors:
        return ValidationResult(ok=False, errors=errors[:MAX_ERRORS])
    return ValidationResult(ok=True, operations=ops)
