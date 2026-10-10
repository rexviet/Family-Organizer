import pytest

SECRET = "s" * 40


@pytest.fixture(autouse=True)
def _env_sach(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không để env của máy dev (AGENT_*, OPENAI_*) lọt vào test."""
    import os

    for k in list(os.environ):
        if k.startswith(("AGENT_", "OPENAI_")) or k == "APP_INTERNAL_URL":
            monkeypatch.delenv(k)


def build_settings(**kw: object):  # type: ignore[no-untyped-def]
    """Settings(...) theo tên trường → truyền qua alias env (Settings không nhận tên trường trực tiếp)."""
    from family_agent.settings import Settings

    return Settings(**{str(Settings.model_fields[k].validation_alias): v for k, v in kw.items()})
