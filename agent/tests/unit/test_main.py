from typing import Any

import pytest

from family_agent import __main__ as entry
from tests.conftest import SECRET


def test_main_chay_uvicorn_cong_3100(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: calls.append({"app": app, **kw}))
    entry.main()
    assert len(calls) == 1
    kw = calls[0]
    assert kw["host"] == "0.0.0.0" and kw["port"] == 3100
    assert kw["access_log"] is False  # log riêng một dòng/lượt, không log URL/header
    assert kw["server_header"] is False


def test_main_thieu_secret_thoat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(entry.uvicorn, "run", lambda *a, **k: pytest.fail("không được chạy server"))
    with pytest.raises(SystemExit):
        entry.main()
