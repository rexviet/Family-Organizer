import pytest
from pydantic import ValidationError

from family_agent.settings import Settings, load_settings
from tests.conftest import SECRET, build_settings


def test_doc_tu_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    monkeypatch.setenv("AGENT_LLM_BASE_URL", "http://llm.local/v1")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "sk-bi-mat")
    monkeypatch.setenv("AGENT_LLM_MODEL", "kr/deepseek-3.2")
    monkeypatch.setenv("AGENT_LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("AGENT_LLM_MAX_TOKENS", "2000")
    monkeypatch.setenv("APP_INTERNAL_URL", "http://app:3000")
    monkeypatch.setenv("AGENT_VERSION", "1.2.3")
    s = Settings()
    assert s.llm_configured
    assert s.llm_model == "kr/deepseek-3.2"
    assert s.llm_temperature == 0.2
    assert s.llm_max_tokens == 2000
    assert s.llm_timeout_s == 60
    assert s.app_internal_url == "http://app:3000"
    assert s.version == "1.2.3"
    assert s.run_timeout_s == 90
    assert s.max_concurrent_runs == 2


def test_env_rong_coi_nhu_khong_dat(monkeypatch: pytest.MonkeyPatch) -> None:
    # compose truyền ${X:-} → chuỗi rỗng; không được làm hỏng parse số.
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    for k in ("AGENT_LLM_BASE_URL", "AGENT_LLM_API_KEY", "AGENT_LLM_MODEL", "AGENT_LLM_TEMPERATURE",
              "AGENT_LLM_MAX_TOKENS", "AGENT_LLM_TIMEOUT_S"):
        monkeypatch.setenv(k, "")
    s = Settings()
    assert not s.llm_configured
    assert s.llm_temperature is None
    assert s.llm_timeout_s == 60


@pytest.mark.parametrize("missing", ["llm_base_url", "llm_api_key", "llm_model"])
def test_thieu_mot_bien_llm_la_chua_cau_hinh(missing: str) -> None:
    kw: dict[str, str] = {"llm_base_url": "http://x/v1", "llm_api_key": "k", "llm_model": "m"}
    kw[missing] = "  "
    assert not build_settings(shared_secret=SECRET, **kw).llm_configured


def test_secret_bat_buoc_va_du_32_ky_tu() -> None:
    with pytest.raises(ValidationError):
        Settings()
    with pytest.raises(ValidationError):
        build_settings(shared_secret="x" * 31)


def test_repr_khong_lo_key_va_secret() -> None:
    s = build_settings(shared_secret=SECRET, llm_api_key="sk-bi-mat", llm_base_url="u", llm_model="m")
    assert SECRET not in repr(s) and "sk-bi-mat" not in repr(s)


def test_load_settings_loi_khong_in_gia_tri(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AGENT_SHARED_SECRET", "ngan-qua-lo-ra-la-hong")
    with pytest.raises(SystemExit) as exc:
        load_settings()
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "AGENT_SHARED_SECRET" in err
    assert "ngan-qua-lo-ra-la-hong" not in err


def test_bien_env_khong_tien_to_bi_bo_qua(monkeypatch: pytest.MonkeyPatch) -> None:
    # Biến "lạc" trong stack dùng chung không được đổi endpoint LLM hay gỡ giới hạn.
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    for k, v in {"LLM_BASE_URL": "http://evil/v1", "LLM_API_KEY": "leak", "LLM_MODEL": "m",
                 "RUN_TIMEOUT_S": "99999", "MAX_CONCURRENT_RUNS": "50", "VERSION": "x",
                 "SHARED_SECRET": "y" * 40}.items():
        monkeypatch.setenv(k, v)
    s = Settings()
    assert not s.llm_configured
    assert s.run_timeout_s == 90 and s.max_concurrent_runs == 2 and s.version == "dev"
    assert s.shared_secret.get_secret_value() == SECRET


@pytest.mark.parametrize("bad", [" " * 40, "mật-khẩu-" + "x" * 32, "x" * 32 + "\n", " " + "x" * 32])
def test_secret_phai_ascii_in_duoc_khong_khoang_trang_bien(bad: str) -> None:
    with pytest.raises(ValidationError):
        build_settings(shared_secret=bad)
