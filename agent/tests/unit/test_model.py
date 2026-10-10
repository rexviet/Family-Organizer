from pydantic_ai.models.openai import OpenAIChatModel

from family_agent.model import build_model
from family_agent.settings import Settings
from tests.conftest import SECRET, build_settings


def _settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "shared_secret": SECRET, "llm_base_url": "http://llm.local/v1", "llm_api_key": "sk-x", "llm_model": "m1",
    }
    s: Settings = build_settings(**(base | kw))
    return s


def test_dung_model_openai_tu_settings() -> None:
    m = build_model(_settings(llm_temperature=0.3, llm_max_tokens=1500, llm_timeout_s=45))
    assert isinstance(m, OpenAIChatModel)
    assert m.model_name == "m1"
    assert str(m.client.base_url).startswith("http://llm.local/v1")
    assert m.client.api_key == "sk-x"
    assert m.settings == {"timeout": 45, "temperature": 0.3, "max_tokens": 1500}


def test_tuy_chon_khong_dat_thi_khong_gui() -> None:
    m = build_model(_settings())
    assert m.settings == {"timeout": 60}


def test_gioi_han_retry_cua_client() -> None:
    # Mặc định openai retry 2 lần × timeout 60 s → timeout 90 s của lượt luôn cắt trước.
    assert build_model(_settings()).client.max_retries == 1
