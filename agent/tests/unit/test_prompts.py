"""Instructions: ngày/thứ/múi giờ, khoảng tuần Thứ Hai–Chủ nhật tính bằng code, bảng thành viên, luật đề xuất."""

import httpx

from family_agent.harness.deps import AppDeps, Member, UserInfo
from family_agent.harness.prompts import build_instructions, week_bounds

MEMBERS = [
    Member(id="u_lan", fullName="Mẹ Lan", role="member", relation="Mẹ"),
    Member(id="u_na", fullName="Bé Na", role="child", relation="Con"),
]


def make(today: str = "2026-10-10", weekday: str = "Thứ Bảy", role: str = "member", **kw: object) -> AppDeps:
    return AppDeps(
        http=httpx.AsyncClient(), user=UserInfo("u_lan", "Mẹ Lan", role), today=today, weekday=weekday,
        members=list(MEMBERS), **kw,  # type: ignore[arg-type]
    )


def test_week_bounds_thu_hai_den_chu_nhat() -> None:
    from datetime import date

    assert week_bounds(date(2026, 10, 10)) == (date(2026, 10, 5), date(2026, 10, 11))  # Thứ Bảy
    assert week_bounds(date(2026, 10, 11)) == (date(2026, 10, 5), date(2026, 10, 11))  # Chủ nhật vẫn thuộc tuần đó
    assert week_bounds(date(2026, 10, 5)) == (date(2026, 10, 5), date(2026, 10, 11))  # Thứ Hai


def test_co_ngay_thu_va_mui_gio() -> None:
    text = build_instructions(make())
    assert "2026-10-10" in text and "Thứ Bảy" in text and "Asia/Ho_Chi_Minh" in text


def test_co_khoang_tuan_nay_tuan_sau_thang_nay() -> None:
    text = build_instructions(make())
    assert "tuần này" in text and "2026-10-05" in text and "2026-10-11" in text
    assert "2026-10-12" in text and "2026-10-18" in text  # tuần sau
    assert "2026-10-01" in text and "2026-10-31" in text  # tháng này
    assert "2026-10-11" in text  # ngày mai


def test_co_bang_thanh_vien_va_nguoi_hoi() -> None:
    text = build_instructions(make())
    assert "u_lan" in text and "Mẹ Lan" in text and "Bé Na" in text and "child" in text and "Con" in text
    assert "Người đang hỏi: Mẹ Lan" in text


def test_khong_doc_duoc_thanh_vien_thi_ghi_chu() -> None:
    d = make(members_error="Ứng dụng không phản hồi")
    d.members = []
    text = build_instructions(d)
    assert "không lấy được danh sách thành viên" in text.lower()


def test_co_tu_dien_hang_muc_va_luat_de_xuat() -> None:
    text = build_instructions(make())
    assert "food" in text and "Ăn uống" in text and "utilities" in text
    assert "propose_" in text and "ask_user" in text and "run_code" in text
    assert "id" in text and "list_" in text
    assert "asyncio.gather" in text


def test_tre_em_khong_xem_thu_chi() -> None:
    assert "không xem được thu chi" in build_instructions(make(role="child"))
    assert "không xem được thu chi" in build_instructions(make(role="guest"))
    assert "không xem được thu chi" not in build_instructions(make(role="member"))


def test_co_vi_du_doi_lich_va_giao_viec() -> None:
    text = build_instructions(make())
    assert "propose_update_plan(" in text and "propose_create_task(" in text
    assert "assignee_id=" in text


def test_agent_co_du_6_tool_viec_lich() -> None:
    from family_agent.harness.tools.plans import plan_toolset
    from family_agent.harness.tools.tasks import task_toolset

    names = set(task_toolset.tools) | set(plan_toolset.tools)
    assert names == {
        "propose_create_task", "propose_update_task", "propose_delete_task",
        "propose_create_plan", "propose_update_plan", "propose_delete_plan",
    }


def test_build_agent_dang_ky_toolset_viec_lich() -> None:
    from pydantic_ai.models.test import TestModel

    from family_agent.harness.agent import TurnLimits, build_agent
    from family_agent.harness.tools.plans import plan_toolset
    from family_agent.harness.tools.tasks import task_toolset

    agent = build_agent(TestModel(), TurnLimits())
    assert task_toolset in agent.toolsets and plan_toolset in agent.toolsets


def test_agent_co_3_tool_thu_chi_va_dang_ky() -> None:
    from pydantic_ai.models.test import TestModel

    from family_agent.harness.agent import TurnLimits, build_agent
    from family_agent.harness.tools.finance import finance_toolset

    assert set(finance_toolset.tools) == {
        "propose_create_transaction", "propose_update_transaction", "propose_delete_transaction",
    }
    assert finance_toolset in build_agent(TestModel(), TurnLimits()).toolsets


def test_co_vi_du_ghi_thu_chi_tien_nguyen_van() -> None:
    text = build_instructions(make())
    assert "propose_create_transaction(" in text
    assert 'amount="250k"' in text  # truyền nguyên văn, tool tự đổi
    assert "tự nhân" in text


def test_tre_em_khong_de_xuat_thu_chi() -> None:
    assert "propose_*_transaction" in build_instructions(make(role="child"))
