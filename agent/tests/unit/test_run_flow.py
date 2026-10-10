"""Luồng đầy đủ một lượt với FunctionModel: đọc → đề xuất / hỏi lại / trả lời; history, token, giới hạn."""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

import pytest
import respx
from pydantic_ai.exceptions import ContentFilterError, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from family_agent.harness.agent import (
    TurnInput,
    TurnLimits,
    TurnResult,
    run_turn,
    settle,
    trim_history,
)
from family_agent.harness.deps import AppDeps, UserInfo, build_http_client

pytestmark = pytest.mark.anyio

BASE = "http://app.test:3000"
TOKEN = "agent-token-KHONG-DUOC-LO-123456"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


USERS = {"users": [
    {"id": "u_lan", "username": "lan", "fullName": "Mẹ Lan", "role": "member", "familyRelation": "me",
     "avatarColor": "x", "createdAt": "x"},
    {"id": "u_na", "username": "na", "fullName": "Bé Na", "role": "child", "familyRelation": "con",
     "avatarColor": "x", "createdAt": "x"},
]}
SHOP = {"shoppingItems": [
    {"id": "s1", "name": "Sữa tươi", "quantity": "2 hộp", "isPurchased": False, "creatorId": "u", "createdAt": "x",
     "updatedAt": "2026-10-01T00:00:00.000Z"},
]}


CATS = {"customCategories": [{"id": "cc_pet", "label": "Thú cưng", "emoji": "x", "color": "teal"}],
        "hiddenBuiltinCategories": []}


def inp(
    message: str = "Hôm nay nhà mình có việc gì?", history: list[dict[str, Any]] | None = None, **kw: Any
) -> TurnInput:
    base: dict[str, Any] = {
        "message": message, "history": history or [], "user": UserInfo("u_lan", "Mẹ Lan", "member"),
        "agent_token": TOKEN, "today": "2026-10-10", "weekday": "Thứ Bảy",
    }
    return TurnInput(**(base | kw))


def code(src: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("run_code", {"code": src})])


def text(t: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(t)])


class Script:
    """FunctionModel theo kịch bản; ghi lại thông điệp + instructions mỗi request."""

    def __init__(self, *steps: ModelResponse | Callable[[list[ModelMessage]], ModelResponse]) -> None:
        self.steps = steps
        self.seen: list[list[ModelMessage]] = []
        self.instructions: list[str | None] = []
        self.model = FunctionModel(self._fn)

    def _fn(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.seen.append(list(messages))
        self.instructions.append(info.instructions)
        step = self.steps[min(len(self.seen), len(self.steps)) - 1]
        return step(messages) if callable(step) else step


def mock_app(shop: Any = SHOP, users: Any = USERS) -> respx.MockRouter:
    router = respx.mock(assert_all_called=False)
    router.get(f"{BASE}/api/users").respond(json=users)
    router.get(f"{BASE}/api/shopping").respond(json=shop)
    router.get(f"{BASE}/api/tasks").respond(json={"tasks": []})
    router.get(f"{BASE}/api/finance").respond(403, json={"error": "Forbidden"})
    router.get(f"{BASE}/api/finance/categories").respond(json=CATS)
    return router


async def go(script: Script, i: TurnInput | None = None, limits: TurnLimits | None = None) -> TurnResult:
    return await run_turn(script.model, i or inp(), app_base_url=BASE, limits=limits or TurnLimits())


# --- 3 kind --------------------------------------------------------------------------------

async def test_kind_answer_doc_roi_tra_loi() -> None:
    s = Script(code("await list_tasks(status='open')"), text("Hôm nay chưa có việc nào."))
    with mock_app() as router:
        r = await go(s)
        methods = {c.request.method for c in router.calls}
    assert (r.kind, r.reply) == ("answer", "Hôm nay chưa có việc nào.")
    assert r.operations is None and r.question is None
    assert r.usage["requests"] == 2
    assert methods == {"GET"}  # không có ghi nào


async def test_kind_proposal_reply_do_code_dung() -> None:
    s = Script(code("await propose_add_shopping_items(items=['Sữa chua', 'Sữa tươi'])"), text("KHÔNG ĐƯỢC DÙNG"))
    with mock_app():
        r = await go(s, inp("thêm sữa chua và sữa tươi"))
    assert r.kind == "proposal"
    assert r.operations == [{"type": "shopping.add", "items": [{"name": "Sữa chua"}]}]  # Sữa tươi đã có sẵn
    assert r.reply == "Mình đề xuất 1 thay đổi — bạn xem và bấm Duyệt nhé."
    assert len(s.seen) == 1  # EndWhenSettled: không request thứ 2


async def test_kind_clarification_lay_chu_cua_tool() -> None:
    s = Script(code("await ask_user(question='Bạn muốn giao việc cho ai?', options=['Na', 'Bin'])"), text("KHÔNG"))
    with mock_app():
        r = await go(s, inp("giao việc cho bé"))
    assert r.kind == "clarification"
    assert (r.question, r.options) == ("Bạn muốn giao việc cho ai?", ["Na", "Bin"])
    assert r.reply == r.question


async def test_cau_hoi_thang_de_xuat_trong_cung_buoc() -> None:
    s = Script(code(
        "import asyncio\n"
        "await asyncio.gather(propose_add_shopping_items(items=['A']), ask_user(question='Mua loại nào?'))"
    ))
    with mock_app():
        r = await go(s)
    assert r.kind == "clarification" and r.operations is None


# --- members, token, lỗi quyền ---------------------------------------------------------------

async def test_thanh_vien_lay_1_lan_dau_luot_va_vao_instructions() -> None:
    s = Script(code("await list_members()\nawait list_members()"), text("ok"))
    with mock_app() as router:
        await go(s)
        users_calls = [c for c in router.calls if c.request.url.path == "/api/users"]
    assert len(users_calls) == 1
    first = s.instructions[0] or ""
    assert "u_na" in first and "Bé Na" in first and "2026-10-10" in first


async def test_hang_muc_tu_them_lay_1_lan_dau_luot_va_vao_instructions() -> None:
    s = Script(text("ok"))
    with mock_app() as router:
        await go(s)
        cat_calls = [c for c in router.calls if c.request.url.path == "/api/finance/categories"]
    assert len(cat_calls) == 1
    first = s.instructions[0] or ""
    assert "cc_pet = Thú cưng" in first


async def test_con_khong_lay_hang_muc_thu_chi() -> None:
    s = Script(text("ok"))
    with mock_app() as router:
        await go(s, inp(user=UserInfo("u_na", "Bé Na", "child")))
        paths = {c.request.url.path for c in router.calls}
    assert "/api/finance/categories" not in paths


async def test_khong_lay_duoc_hang_muc_van_chay_tiep() -> None:
    s = Script(text("Xin chào"))
    with mock_app() as router:
        router.get(f"{BASE}/api/finance/categories").respond(500, json={})
        r = await go(s)
    assert (r.kind, r.reply) == ("answer", "Xin chào")


async def test_so_tien_khong_don_vi_trong_loi_nguoi_dung_thi_hoi_lai() -> None:
    # eval phase 9 A09: "đi chợ hết 150" → model tự đổi thành "150k" → tool hỏi lại kèm lựa chọn
    s = Script(code("await propose_create_transaction(tx_type='expense', amount='150k', category='food')"))
    with mock_app():
        r = await go(s, inp("Hôm nay đi chợ hết 150"))
    assert r.kind == "clarification" and r.operations is None
    assert r.options == ["150.000đ", "150.000.000đ"]


async def test_so_tien_tra_loi_o_tin_sau_dung_history() -> None:
    first = Script(code("await propose_create_transaction(tx_type='expense', amount='150k', category='food')"))
    with mock_app():
        r1 = await go(first, inp("Hôm nay đi chợ hết 150"))
    second = Script(code("await propose_create_transaction(tx_type='expense', amount='150k', category='food')"))
    with mock_app():
        r2 = await go(second, inp("nghìn", history=r1.history))
    assert r2.kind == "proposal" and r2.operations is not None and r2.operations[0]["amount"] == 150000


@pytest.mark.parametrize("status", [401, 403, 500])
async def test_khong_lay_duoc_thanh_vien_van_chay_tiep(status: int) -> None:
    s = Script(text("Xin chào"))
    with respx.mock(assert_all_called=False) as r2:
        r2.get(f"{BASE}/api/users").respond(status, json={})
        r2.get(f"{BASE}/api/finance/categories").respond(status, json={})
        r = await go(s)
    assert r.kind == "answer"
    assert "không lấy được danh sách thành viên" in (s.instructions[0] or "").lower()


async def test_token_khong_bao_gio_lo_ra() -> None:
    s = Script(
        code(
            "await list_members()\nawait list_shopping()\n"
            "await search_transactions(date_from='2026-10-01', date_to='2026-10-31')"
        ),
        code("await propose_add_shopping_items(items=['Trứng'])"),
    )
    with mock_app() as router:
        r = await go(s)
        auth = [c.request.headers["authorization"] for c in router.calls]
    blob = json.dumps({"reply": r.reply, "ops": r.operations, "history": r.history, "usage": r.usage})
    assert TOKEN not in blob
    assert all(TOKEN not in (i or "") for i in s.instructions)
    assert all(TOKEN not in repr(m) for seen in s.seen for m in seen)
    assert auth and all(a == f"Bearer {TOKEN}" for a in auth)


async def test_403_thu_chi_model_thay_loi_tieng_viet_va_luot_khong_hong() -> None:
    def after_error(messages: list[ModelMessage]) -> ModelResponse:
        returns = [p for m in messages for p in m.parts if p.part_kind in ("tool-return", "retry-prompt")]
        assert "không có quyền" in str(returns[-1].content)
        return text("Tài khoản của bạn không xem được thu chi.")

    s = Script(code("await search_transactions(date_from='2026-10-01', date_to='2026-10-31')"), after_error)
    with mock_app():
        r = await go(s, inp("tháng này chi bao nhiêu?"))
    assert r.kind == "answer" and "không xem được" in r.reply


# --- output validator ------------------------------------------------------------------------------

@pytest.mark.parametrize("claim", [
    "Mình đã thêm sữa vào danh sách.", "Da xoa mon do roi", "Đã xóa xong", "Đã tạo việc mới",
    "Đã cập nhật lịch", "Mình đã ghi khoản chi",
])
async def test_noi_da_lam_ma_khong_co_de_xuat_bi_ModelRetry(claim: str) -> None:
    s = Script(text(claim), text("Mình chưa thay đổi gì cả."))
    with mock_app():
        r = await go(s)
    assert len(s.seen) == 2  # bị gửi lại một lần
    retry = [p for m in s.seen[1] for p in m.parts if p.part_kind == "retry-prompt"]
    assert retry and "propose_" in str(retry[0].content)
    assert r.reply.startswith("Mình chưa thay đổi")


async def test_cau_tra_loi_binh_thuong_khong_bi_retry() -> None:
    s = Script(text("Hôm nay có 2 việc: đánh răng, làm bài."))
    with mock_app():
        await go(s)
    assert len(s.seen) == 1


# --- giới hạn -------------------------------------------------------------------------------------------

async def test_vuot_request_limit_tra_answer_tieng_viet() -> None:
    s = Script(code("await list_tasks()"))  # lặp mãi run_code
    with mock_app():
        r = await go(s, inp("tổng hợp giúp mình"), TurnLimits(request_limit=3))
    assert r.kind == "answer" and "hỏi gọn" in r.reply
    msgs = ModelMessagesTypeAdapter.validate_python(r.history)
    assert isinstance(msgs[-1], ModelResponse) and msgs[-1].parts[0].content == r.reply  # type: ignore[union-attr]
    first = msgs[0]
    assert isinstance(first, ModelRequest) and isinstance(first.parts[0], UserPromptPart)


# --- settle: fail closed, None ------------------------------------------------------------------------------

def bare_deps() -> AppDeps:
    http = build_http_client(BASE, TOKEN)
    return AppDeps(http=http, user=UserInfo("u", "n", "admin"), today="2026-10-10", weekday="T")


def test_settle_operation_sai_hop_dong_khong_tra_proposal() -> None:
    d = bare_deps()
    d.outcome.operations.append({"type": "shopping.add", "items": [{"name": ""}]})  # lọt qua add() (giả lập lỗi code)
    kind, reply, ops, _q, _o = settle(d, None)
    assert kind == "answer" and ops is None and "diễn đạt lại" in reply


def test_settle_output_none_va_rong_co_cau_tra_loi_du_phong() -> None:
    d = bare_deps()
    for out in (None, "", "   "):
        kind, reply, *_ = settle(d, out)
        assert kind == "answer" and reply


def test_settle_so_nhieu_thay_doi() -> None:
    d = bare_deps()
    d.outcome.add({"type": "shopping.add", "items": [{"name": "A"}]})
    d.outcome.add({"type": "shopping.delete", "itemId": "x", "base": {"updatedAt": "t"}})
    assert settle(d, None)[1] == "Mình đề xuất 2 thay đổi — bạn xem và bấm Duyệt nhé."


# --- history ------------------------------------------------------------------------------------------------------

def user_turn(i: int, with_tool: bool = True) -> list[ModelMessage]:
    msgs: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart(f"câu {i}")])]
    if with_tool:
        msgs += [
            ModelResponse(parts=[ToolCallPart("run_code", {"code": "1"}, tool_call_id=f"c{i}")]),
            ModelRequest(parts=[ToolReturnPart("run_code", "1", tool_call_id=f"c{i}")]),
        ]
    msgs.append(ModelResponse(parts=[TextPart(f"đáp {i}")]))
    return msgs


def n_user_turns(msgs: list[ModelMessage]) -> int:
    return sum(1 for m in msgs if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts))


def test_trim_history_chi_cat_o_ranh_gioi_tin_nhan_nguoi_dung() -> None:
    msgs = [m for i in range(25) for m in user_turn(i)]
    out = trim_history(msgs, 20)
    assert n_user_turns(out) == 20
    first = out[0]
    assert isinstance(first, ModelRequest) and isinstance(first.parts[0], UserPromptPart)
    assert first.parts[0].content == "câu 5"
    assert out[-1] == msgs[-1]


def test_trim_history_ngan_thi_giu_nguyen() -> None:
    msgs = [m for i in range(3) for m in user_turn(i)]
    assert trim_history(msgs, 20) == msgs


def test_trim_history_luot_dang_ket_thuc_bang_tool_return_van_dung_ranh_gioi() -> None:
    msgs = [m for i in range(21) for m in user_turn(i)]
    msgs.pop()  # lượt cuối kết thúc bằng tool-return (EndWhenSettled)
    out = trim_history(msgs, 20)
    assert n_user_turns(out) == 20 and not isinstance(out[0].parts[0], ToolReturnPart)


async def test_history_tra_ve_gom_luot_moi_va_cat_20_luot() -> None:
    old = ModelMessagesTypeAdapter.dump_python([m for i in range(24) for m in user_turn(i)], mode="json")
    s = Script(text("Chào"))
    with mock_app():
        r = await go(s, inp("câu mới", history=old))
    msgs = ModelMessagesTypeAdapter.validate_python(r.history)
    assert n_user_turns(msgs) == 20
    assert isinstance(msgs[-1], ModelResponse) and msgs[-1].parts[0].content == "Chào"  # type: ignore[union-attr]
    assert all(getattr(m, "instructions", None) is None for m in msgs)  # không phình theo instructions


async def test_luot_sau_de_xuat_noi_tiep_duoc_va_thay_loi_dan() -> None:
    s1 = Script(code("await propose_add_shopping_items(items=['Trứng'])"))
    with mock_app():
        first = await go(s1, inp("thêm trứng"))
    assert first.kind == "proposal"
    s2 = Script(text("Ok"))
    with mock_app():
        second = await go(s2, inp("thêm cả hành nữa", history=first.history))
    assert second.kind == "answer"
    seen = s2.seen[0]
    assert n_user_turns(seen) == 2
    assert any("bấm Duyệt" in str(p.content) for m in seen for p in m.parts if p.part_kind == "text")


# --- review: H2 (validator không bắt câu đọc thường) -------------------------------------------------

@pytest.mark.parametrize("answer", [
    "Mẹ đã ghi 3 khoản chi tháng này, tổng 500.000đ.",
    "Lan đã tạo việc này hôm qua.",
    "Bé Na đã mua sữa rồi, còn thiếu dầu ăn.",
    "Các món đã mua:\n- Gạo\n- Sữa",
    "Bố Minh đã xoá việc cũ từ tuần trước.",
])
async def test_cau_tra_loi_doc_ngoi_thu_ba_khong_bi_retry(answer: str) -> None:
    s = Script(text(answer))
    with mock_app():
        r = await go(s)
    assert len(s.seen) == 1 and r.reply == answer


@pytest.mark.parametrize("claim", [
    "Mình đã thêm sữa", "Vâng, đã xóa rồi nhé", "Tôi đã đánh dấu món đó là đã mua", "Em đã sửa lịch cho mẹ",
    "OK, mình đã giao việc cho Na", "Xong. Đã tạo việc mới",
])
async def test_khang_dinh_ngoi_thu_nhat_van_bi_retry(claim: str) -> None:
    s = Script(text(claim), text("Mình chưa thay đổi gì."))
    with mock_app():
        await go(s)
    assert len(s.seen) == 2


async def test_model_khang_dinh_mai_thi_tra_answer_than_thien_khong_502() -> None:
    s = Script(text("Mình đã thêm sữa"))  # lặp mãi → hết output retries
    with mock_app():
        r = await go(s, inp("thêm sữa"))
    assert r.kind == "answer" and "diễn đạt lại" in r.reply
    msgs = ModelMessagesTypeAdapter.validate_python(r.history)
    assert isinstance(msgs[-1], ModelResponse) and msgs[-1].parts[0].content == r.reply  # type: ignore[union-attr]


async def test_code_loi_mai_thi_tra_answer_than_thien() -> None:
    s = Script(code("1 +"))
    with mock_app():
        r = await go(s)
    assert r.kind == "answer" and "diễn đạt lại" in r.reply


# --- review: H1 (ngân sách code theo lượt) -------------------------------------------------------------

async def test_nhieu_run_code_va_restart_khong_keo_dai_treo_event_loop() -> None:
    n = {"i": 0}

    def fn(_m: list[ModelMessage]) -> ModelResponse:
        n["i"] += 1
        if n["i"] <= 3:
            return ModelResponse(parts=[
                ToolCallPart(
                    "run_code", {"code": "while True:\n    pass", "restart": k > 0}, tool_call_id=f"c{n['i']}{k}",
                )
                for k in range(3)
            ])
        return text("xong")

    gaps: list[float] = []
    stop = asyncio.Event()

    async def ticker() -> None:
        last = time.monotonic()
        while not stop.is_set():
            await asyncio.sleep(0.01)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    budget = 0.3
    s = Script(fn)
    tick = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    started = time.monotonic()
    with mock_app():
        await go(s, limits=TurnLimits(code_max_duration_s=budget))
    elapsed = time.monotonic() - started
    stop.set()
    await tick
    assert max(gaps) <= budget + 0.25  # một lần treo liên tục ≈ một ngân sách
    assert sum(g for g in gaps if g > 0.1) <= 2 * budget + 0.3  # tổng cả lượt có chặn trên
    assert elapsed <= 2 * budget + 1.0


async def test_hai_run_code_trong_cung_mot_phan_hoi_chi_chay_cai_dau() -> None:
    calls = {"n": 0}

    def fn(msgs: list[ModelMessage]) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(parts=[
                ToolCallPart("run_code", {"code": "await list_tasks()"}, tool_call_id="a"),
                ToolCallPart("run_code", {"code": "await list_shopping()"}, tool_call_id="b"),
            ])
        returns = {
            p.tool_call_id: str(p.content)
            for m in msgs for p in m.parts if p.part_kind in ("tool-return", "retry-prompt")
        }
        assert "một run_code" in returns["b"]
        return text("ok")

    with mock_app() as router:
        await go(Script(fn))
        paths = [c.request.url.path for c in router.calls]
    assert "/api/shopping" not in paths and "/api/tasks" in paths


async def test_het_ngan_sach_thi_tu_choi_run_code_bang_cau_co_dinh() -> None:
    seen: list[str] = []
    n = {"i": 0}

    def fn(msgs: list[ModelMessage]) -> ModelResponse:
        n["i"] += 1
        if n["i"] == 1:
            return code("while True:\n    pass")
        if n["i"] == 2:
            return code("1 + 1")
        seen.extend(str(p.content) for m in msgs for p in m.parts if p.part_kind == "retry-prompt")
        return text("ok")

    with mock_app():
        await go(Script(fn), limits=TurnLimits(code_max_duration_s=0.2))
    assert any("hết thời gian chạy code" in c for c in seen)


# --- review: M1 (đề xuất dở dang) ---------------------------------------------------------------------------

async def test_propose_sau_loi_thi_hoan_tac_va_khong_ket_thuc_luot() -> None:
    items = [f"Món {i}" for i in range(31)]
    n = {"i": 0}

    def fn(msgs: list[ModelMessage]) -> ModelResponse:
        n["i"] += 1
        if n["i"] == 1:
            return code(
                "await propose_remove_shopping_items(item_ids=['s1'])\n"
                f"await propose_add_shopping_items(items={items!r})"
            )
        return text("Mình chưa đề xuất được vì quá nhiều món.")

    with mock_app():
        r = await go(Script(fn))
    assert r.kind == "answer" and r.operations is None
    assert n["i"] == 2  # model nhận lỗi và được trả lời tiếp, không bị kết thúc sớm với đề xuất một nửa


# --- review: M4 (giới hạn kích thước history) ---------------------------------------------------------------

async def test_history_qua_lon_thi_bo_nguyen_luot_cu_nhat() -> None:
    big = "x" * 20_000
    turns = [m for i in range(10) for m in user_turn(i, with_tool=False)]
    old = ModelMessagesTypeAdapter.dump_python(turns, mode="json")
    for m in old:
        for p in m["parts"]:
            if p["part_kind"] == "text":
                p["content"] = big
    s = Script(text("Chào"))
    with mock_app():
        r = await go(s, inp("câu mới", history=old), TurnLimits(max_history_bytes=100_000))
    assert len(json.dumps(r.history)) <= 100_000
    msgs = ModelMessagesTypeAdapter.validate_python(r.history)
    first = msgs[0]
    assert isinstance(first, ModelRequest) and isinstance(first.parts[0], UserPromptPart)
    assert isinstance(msgs[-1], ModelResponse) and msgs[-1].parts[0].content == "Chào"  # type: ignore[union-attr]


# --- review: L7 --------------------------------------------------------------------------------------------------

def test_load_history_bo_system_prompt_cu() -> None:
    from pydantic_ai.messages import SystemPromptPart

    from family_agent.harness.agent import load_history

    raw = ModelMessagesTypeAdapter.dump_python([
        ModelRequest(parts=[SystemPromptPart("BÍ MẬT CŨ"), UserPromptPart("hi")]),
        ModelResponse(parts=[TextPart("chào")]),
        ModelRequest(parts=[SystemPromptPart("chỉ có system")]),
    ], mode="json")
    out = load_history(raw)
    assert "BÍ MẬT CŨ" not in repr(out) and len(out) == 2
    assert all(p.part_kind != "system-prompt" for m in out for p in m.parts)


# --- review 2 ---------------------------------------------------------------------------------------------------------

def _retry_prompts(msgs: list[ModelMessage]) -> list[str]:
    return [str(p.content) for m in msgs for p in m.parts if p.part_kind == "retry-prompt"]


async def test_try_except_quanh_propose_van_hoan_tac_het_va_bao_model() -> None:
    items = [f"Món {i}" for i in range(31)]
    n = {"i": 0}
    seen: list[str] = []

    def fn(msgs: list[ModelMessage]) -> ModelResponse:
        n["i"] += 1
        if n["i"] == 1:
            return code(
                "await propose_remove_shopping_items(item_ids=['s1'])\n"
                "try:\n"
                f"    await propose_add_shopping_items(items={items!r})\n"
                "except Exception:\n"
                "    pass\n"
                "'xong'"
            )
        seen.extend(_retry_prompts(msgs))
        return text("Mình chưa đề xuất được vì quá nhiều món.")

    with mock_app():
        r = await go(Script(fn))
    assert r.kind == "answer" and r.operations is None and n["i"] == 2
    assert seen and "HUỶ" in seen[0]


async def test_loi_giua_chung_bao_cho_model_biet_da_hoan_tac() -> None:
    n = {"i": 0}
    seen: list[str] = []

    def fn(msgs: list[ModelMessage]) -> ModelResponse:
        n["i"] += 1
        if n["i"] == 1:
            return code("await propose_remove_shopping_items(item_ids=['s1'])\n1/0")
        seen.extend(_retry_prompts(msgs))
        return text("ok")

    with mock_app():
        await go(Script(fn))
    assert seen and "HUỶ" in seen[0] and "gọi lại đầy đủ" in seen[0]


@pytest.mark.parametrize("claim", [
    "Mình đã đề xuất thêm sữa vào danh sách rồi nhé.",
    "Mình đã thêm sữa".replace("ì", "i\u0300").replace("đ", "đ"),  # NFD: "i" + dấu huyền rời
    "Tôi đã đánh dấu xong".replace("ô", "o\u0302"),
])
async def test_khang_dinh_de_xuat_hoac_nfd_van_bi_retry(claim: str) -> None:
    s = Script(text(claim), text("Mình chưa thay đổi gì."))
    with mock_app():
        await go(s)
    assert len(s.seen) == 2


@pytest.mark.parametrize("error", [
    ContentFilterError("blocked by provider"),
    UnexpectedModelBehavior("Received empty model response"),
])
async def test_loi_phia_provider_van_nem_ra_de_app_tra_502(error: Exception) -> None:
    def boom(_m: list[ModelMessage]) -> ModelResponse:
        raise error

    with mock_app(), pytest.raises(UnexpectedModelBehavior):
        await go(Script(boom))


# --- hỏi lại bằng chữ → nhắc dùng ask_user (eval phase 9: model hỏi trong câu trả lời, không có nút chọn) -----------

def _retry_texts(msgs: list[ModelMessage]) -> list[str]:
    from pydantic_ai.messages import RetryPromptPart

    return [str(p.content) for m in msgs if isinstance(m, ModelRequest) for p in m.parts
            if isinstance(p, RetryPromptPart)]


async def test_hoi_bang_chu_thi_nhac_ask_user_mot_lan() -> None:
    s = Script(
        text("Bạn muốn thêm món gì vào danh sách?"),
        code("await ask_user(question='Bạn muốn thêm món gì?', options=['Sữa', 'Trứng'])"),
    )
    with mock_app():
        r = await go(s, inp("Thêm cái đó vào danh sách nhé"))
    assert r.kind == "clarification" and r.options == ["Sữa", "Trứng"]
    assert any("ask_user" in t for t in _retry_texts(s.seen[1]))


async def test_cau_tra_loi_co_du_lieu_giu_nguyen_neu_model_tra_lai() -> None:
    reply = "Bé Na có 2 việc hôm nay. Bạn có muốn xem thêm không?"
    s = Script(text(reply), text(reply))
    with mock_app():
        r = await go(s)
    assert (r.kind, r.reply) == ("answer", reply)
    assert len(s.seen) == 2  # chỉ nhắc một lần


async def test_cau_tra_loi_khong_hoi_thi_khong_nhac() -> None:
    s = Script(text("Hôm nay chưa có việc nào."))
    with mock_app():
        r = await go(s)
    assert r.kind == "answer" and len(s.seen) == 1
