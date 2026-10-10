"""contract.py phải ra đúng các chuỗi/hash trong agent/contracts/vectors.json (Node cũng chạy bộ này)."""

import json
from pathlib import Path

import pytest

from family_agent import contract

VECTORS = json.loads(
    (Path(__file__).resolve().parents[2] / "contracts" / "vectors.json").read_text(encoding="utf-8")
)


def _ids(items: list[dict]) -> list[str]:
    return [v["name"] for v in items]


def test_contract_version_khop_vectors() -> None:
    assert contract.CONTRACT_VERSION == VECTORS["contractVersion"]


@pytest.mark.parametrize("v", VECTORS["canonical"], ids=_ids(VECTORS["canonical"]))
def test_canonical(v: dict) -> None:
    assert contract.canonical(v["value"]) == v["canonical"]


@pytest.mark.parametrize("v", VECTORS["planHash"], ids=_ids(VECTORS["planHash"]))
def test_plan_hash_va_operation_hop_le(v: dict) -> None:
    assert contract.canonical(v["operations"]) == v["canonical"]
    assert contract.plan_hash(v["operations"]) == v["planHash"]
    result = contract.validate_operations(v["operations"])
    assert result.ok, result.errors
    assert contract.plan_hash(result.operations) == v["planHash"]


@pytest.mark.parametrize("v", VECTORS["fingerprint"], ids=_ids(VECTORS["fingerprint"]))
def test_fingerprint(v: dict) -> None:
    assert contract.fingerprint(v["kind"], v["record"]) == v["fingerprint"]


@pytest.mark.parametrize("v", VECTORS["invalid"], ids=_ids(VECTORS["invalid"]))
def test_invalid_bi_tu_choi(v: dict) -> None:
    result = contract.validate_operations(v["operations"])
    assert not result.ok
    assert result.errors


@pytest.mark.parametrize(
    "value",
    [1.0, 1.5, float("nan"), 2**53, -(2**53), "\ud800", {"k": "\udc00"}, {"\ud800": 1}, {1: 1}, (1,), b"x"],
)
def test_canonical_tu_choi_kieu_ngoai_hop_dong(value: object) -> None:
    with pytest.raises(ValueError):
        contract.canonical(value)


def test_canonical_bool_khong_phai_so() -> None:
    assert contract.canonical([True, False, 0, 1]) == "[true,false,0,1]"


def test_validator_tra_ban_sao_doc_lap() -> None:
    ops = [{"type": "shopping.add", "items": [{"name": "Sữa"}]}]
    result = contract.validate_operations(ops)
    assert result.ok
    result.operations[0]["items"][0]["name"] = "đổi"
    assert ops[0]["items"][0]["name"] == "Sữa"


def test_validator_tu_choi_so_thuc_dang_nguyen() -> None:
    ops = [{"type": "finance.create", "txType": "expense", "amount": 1000.0, "category": "Ăn uống",
            "date": "2026-10-10", "description": "x"}]
    assert not contract.validate_operations(ops).ok


def test_validator_tu_choi_bool_o_truong_so() -> None:
    ops = [{"type": "task.create", "title": "x", "rewardPoints": True}]
    assert not contract.validate_operations(ops).ok


def test_validator_dem_do_dai_theo_code_point() -> None:
    # 100 emoji = 100 code point (200 code unit UTF-16) → vẫn hợp lệ với maxLength 100.
    ops = [{"type": "shopping.add", "items": [{"name": "🛒" * 100}]}]
    assert contract.validate_operations(ops).ok
    ops[0]["items"][0]["name"] = "🛒" * 101
    assert not contract.validate_operations(ops).ok


def test_validator_gioi_han_so_loi() -> None:
    ops = [{"type": "shopping.add", "items": [{"name": "", "x": i} for i in range(20)]}] * 10
    result = contract.validate_operations(ops)
    assert not result.ok
    assert len(result.errors) <= 50


def test_schema_pattern_phai_co_neo() -> None:
    # fullmatch chỉ tương đương RegExp.test của Node khi pattern có ^…$.
    with pytest.raises(ValueError):
        contract._assert_supported({"type": "string", "pattern": "[0-9]+"}, "#")
