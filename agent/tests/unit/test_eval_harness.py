"""Bộ eval phase 9 (agent/eval/run_eval.py — không chạy bởi pytest): luật chấm, bộ câu hợp lệ với dữ liệu giả,
và một lượt chạy trọn đường ống bằng FunctionModel (không cần model thật) — để eval với model thật không hỏng vì lỗi
của khung."""

import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from family_agent.contract import validate_operations
from family_agent.harness.agent import TurnResult

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))
import run_eval as ev  # noqa: E402

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def result(kind: str, reply: str = "", operations: list[dict[str, Any]] | None = None) -> TurnResult:
    return TurnResult(kind, reply, [], {"requests": 1, "toolCalls": 1}, operations=operations)  # type: ignore[arg-type]


CASES = {c["id"]: c for c in ev.load_cases()}
FIXTURE = ev.load_fixture()


# --- bộ câu ---------------------------------------------------------------------------------------------------------

def test_bo_cau_du_va_hop_le() -> None:
    cases = list(CASES.values())
    assert len(cases) >= 50
    assert len(CASES) == len(cases)  # id không trùng
    cats = {c["category"] for c in cases}
    assert cats == {"read", "write", "compound", "ambiguous", "forbidden"}
    modules = {o["type"].split(".")[0] for c in cases for o in c["expect"].get("ops", [])}
    assert modules == {"shopping", "task", "plan", "finance"}
    users = {u["id"]: u["role"] for u in FIXTURE["/api/users"]["users"]}
    assert all(c.get("user", "m2") in users for c in cases)
    assert all(users[c["user"]] == "child" for c in cases if c["category"] == "forbidden")
    assert all(c["expect"].get("ops") for c in cases if c["category"] in ("write", "compound"))


def test_id_trong_cau_ky_vong_ton_tai_trong_du_lieu_gia() -> None:
    ids = {r["id"] for v in FIXTURE.values() if isinstance(v, dict) for rows in v.values() if isinstance(rows, list)
           for r in rows if isinstance(r, dict) and "id" in r}
    for c in CASES.values():
        for op in c["expect"].get("ops", []):
            for key in ("itemId", "taskId", "planId", "txId", "assigneeId"):
                if key in op:
                    assert op[key] in ids, (c["id"], key)


def test_mon_ky_vong_them_chua_co_trong_danh_sach() -> None:
    # S01 cũ kỳ vọng thêm "trứng" trong khi fixture đã có Trứng chưa mua — tool cố ý bỏ qua món đã có → câu luôn FAIL
    from family_agent.harness.vocab import fold

    have = {fold(i["name"]) for i in FIXTURE["/api/shopping"]["shoppingItems"] if not i["isPurchased"]}
    for c in CASES.values():
        for op in c["expect"].get("ops", []):
            if op["type"] == "shopping.add":
                assert not [w for w in op["items~"] if fold(w) in have], c["id"]


# --- đọc số ---------------------------------------------------------------------------------------------------------

def test_numbers_in_doc_nhieu_cach_viet() -> None:
    text = "Tháng này chi 2.720.000đ (khoảng 2,72 triệu), ăn uống 370k, tuần này 1tr520, nhà có 4 người, thu 15 triệu."
    nums = ev.numbers_in(text)
    assert {2_720_000, 370_000, 1_520_000, 4, 15_000_000} <= nums


def test_numbers_in_khong_bia_so_tu_dau_thap_phan() -> None:
    # review M3: "1,5" / "2.5" không được thành 15 / 25
    assert not {15, 25} & ev.numbers_in("Khoảng 1,5 lần, tăng 2.5 điểm")


# --- chấm -----------------------------------------------------------------------------------------------------------

def test_cham_doc() -> None:
    c = CASES["R06"]
    assert ev.score(c, result("answer", "Tháng này nhà mình chi tổng 2.720.000 đ.")).ok
    assert not ev.score(c, result("answer", "Tháng này chi 2.700.000 đ.")).ok
    assert not ev.score(c, result("proposal", "2.720.000")).ok
    c3 = CASES["R03"]
    assert ev.score(c3, result("answer", "Còn Sữa tươi, Dầu ăn, Trứng.")).ok
    assert not ev.score(c3, result("answer", "Còn Sữa tươi, Dầu ăn, Trứng, Gạo.")).ok
    assert ev.score(CASES["R13"], result("answer", "Sinh nhật bà vào 18:00 ngày 20/10.")).ok


def test_cham_ghi_bo_qua_thu_tu_va_truong_tuy_chon() -> None:
    c = CASES["C02"]
    ops = [
        {"type": "shopping.delete", "itemId": "s4", "base": {"updatedAt": "x"}},
        {"type": "finance.create", "txType": "expense", "amount": 250000, "category": "food", "date": "2026-10-10",
         "description": "Đi chợ"},
    ]
    assert ev.score(c, result("proposal", operations=ops)).ok
    assert not ev.score(c, result("proposal", operations=ops[:1])).ok


def test_cham_changes_khong_duoc_doi_them_truong() -> None:
    c = CASES["T04"]
    good = [{"type": "task.update", "taskId": "t3", "changes": {"assigneeId": "m4"}, "base": {"updatedAt": "x"}}]
    extra = [{"type": "task.update", "taskId": "t3", "changes": {"assigneeId": "m4", "title": "Dọn"},
              "base": {"updatedAt": "x"}}]
    assert ev.score(c, result("proposal", operations=good)).ok
    assert not ev.score(c, result("proposal", operations=extra)).ok
    # endDate? = tuỳ chọn: có thì phải đúng
    p = CASES["P02"]
    base = {"type": "plan.update", "planId": "p1", "base": {"fingerprint": "f"}}
    assert ev.score(p, result("proposal", operations=[{**base, "changes": {"startDate": "2026-10-11 15:00"}}])).ok
    assert ev.score(p, result("proposal", operations=[
        {**base, "changes": {"startDate": "2026-10-11 15:00", "endDate": "2026-10-11 17:00"}}])).ok
    assert not ev.score(p, result("proposal", operations=[
        {**base, "changes": {"startDate": "2026-10-11 15:00", "endDate": "2026-10-11 16:00"}}])).ok


def test_cham_items_va_hau_to() -> None:
    assert ev.score(CASES["S01"], result("proposal", operations=[
        {"type": "shopping.add", "items": [{"name": "Chanh", "quantity": "2 chục"}, {"name": "Sữa chua"}]}])).ok
    assert not ev.score(CASES["S01"], result("proposal", operations=[
        {"type": "shopping.add", "items": [{"name": "Chanh"}]}])).ok
    op = {"type": "plan.create", "title": "Tập võ", "startDate": "2026-10-13 17:00", "endDate": "2027-10-13 18:00",
          "recurrenceType": "weekly", "recurrenceWeekdays": [2, 4]}
    assert ev.score(CASES["P04"], result("proposal", operations=[op])).ok
    assert not ev.score(CASES["P04"], result("proposal", operations=[{**op, "startDate": "2026-10-13 18:00"}])).ok
    # Cố ý KHÔNG chấp nhận tách thành 2 lịch [2] + [4]: app hỗ trợ 1 lịch nhiều thứ; 2 bản ghi = sửa/xoá phải làm 2 lần
    split = [{**op, "recurrenceWeekdays": [2]}, {**op, "startDate": "2026-10-15 17:00", "recurrenceWeekdays": [4]}]
    assert not ev.score(CASES["P04"], result("proposal", operations=split)).ok


def test_mo_ho_phai_hoi_lai() -> None:
    c = CASES["A04"]
    assert ev.score(c, result("clarification", "Khoản chi này thuộc hạng mục nào?")).ok
    soft = ev.score(c, result("answer", "Bạn chi 200k cho việc gì vậy?"))
    assert not soft.ok and soft.lenient
    assert not ev.score(c, result("proposal", operations=[{"type": "finance.create"}])).lenient


def test_vuot_quyen() -> None:
    c = CASES["X02"]
    assert ev.score(c, result("answer", "Con chưa xem được thu chi nhé.")).ok
    assert not ev.score(c, result("answer", "Tháng này chi 2.720.000 đ")).ok
    assert not ev.score(CASES["X01"], result("proposal", operations=[{"type": "finance.create"}])).ok


def test_dem_sai_so_tien() -> None:
    def fin(amount: int) -> list[dict[str, Any]]:
        return [{"type": "finance.create", "txType": "expense", "amount": amount, "category": "food",
                 "date": "2026-10-10", "description": "x"}]

    assert ev.money_errors(CASES["F01"], result("proposal", operations=fin(250000))) == 0
    assert ev.money_errors(CASES["F01"], result("proposal", operations=fin(25000))) == 1
    # review M2: thu chi ở câu không chờ thu chi (vd. đoán hạng mục thay vì hỏi lại) KHÔNG phải sai số tiền
    assert ev.money_errors(CASES["S01"], result("proposal", operations=fin(1000))) == 0
    assert ev.unexpected_finance(CASES["S01"], result("proposal", operations=fin(1000))) == 1
    assert ev.unexpected_finance(CASES["F01"], result("proposal", operations=fin(250000))) == 0
    upd = [{"type": "finance.update", "txId": "x2", "changes": {"amount": 90000}, "base": {"fingerprint": "f"}}]
    assert ev.money_errors(CASES["F06"], result("proposal", operations=upd)) == 1


def test_bao_cao_markdown() -> None:
    row = ev.Row(CASES["F01"], "proposal", True, True, 0, 1, 1, 2.0, "ops=…", ["GET"])
    text = ev.render_report("kr/x", [[row], [row]], "2026-10-10")
    assert "| 1 | **1/1** | 100% |" in text and "| 2 |" in text and "F01" in text
    assert ev.slug("kr/claude-haiku-4.5") == "kr-claude-haiku-4.5"


# --- trọn đường ống, không cần model thật ---------------------------------------------------------------------------

def scripted(*steps: ModelResponse) -> FunctionModel:
    seen: list[int] = []

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append(1)
        return steps[min(len(seen), len(steps)) - 1]

    return FunctionModel(fn)


def code(src: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("run_code", {"code": src})])


async def test_chay_mot_cau_ghi_thu_chi_qua_run_turn() -> None:
    model = scripted(code(
        'await propose_create_transaction(tx_type="expense", amount="250k", category="food", description="Đi chợ")'
    ))
    row = await ev.run_case(model, CASES["F01"], FIXTURE)
    assert (row.kind, row.ok, row.money_errors) == ("proposal", True, 0), row.note
    assert row.methods and set(row.methods) == {"GET"}


async def test_chay_cau_sua_thu_chi_base_tu_du_lieu_gia() -> None:
    model = scripted(code('await propose_update_transaction(transaction="Tiền điện tháng 9", amount="900 nghìn")'))
    row = await ev.run_case(model, CASES["F06"], FIXTURE)
    assert row.ok, row.note


async def test_con_doc_thu_chi_bi_403_va_khong_de_xuat() -> None:
    model = scripted(code("await search_transactions(date_from='2026-10-01', date_to='2026-10-31')"),
                     ModelResponse(parts=[TextPart("Con chưa xem được thu chi nhé.")]))
    row = await ev.run_case(model, CASES["X02"], FIXTURE)
    assert row.ok and row.kind == "answer", row.note


def test_ops_hop_dong_trong_cau_ky_vong_khong_tu_mau_thuan() -> None:
    # Kỳ vọng ghi thu chi phải là số nguyên dương (chính là thứ hợp đồng chấp nhận).
    for c in CASES.values():
        for op in c["expect"].get("ops", []):
            if op["type"] == "finance.create":
                full = {"type": "finance.create", "txType": op["txType"], "amount": op["amount"],
                        "category": "food", "date": "2026-10-10", "description": "x"}
                assert validate_operations([full]).ok, c["id"]
