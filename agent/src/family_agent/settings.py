"""Cấu hình agent — chỉ từ env (pydantic-settings). Key/URL/model LLM không bao giờ đi qua Node."""

from __future__ import annotations

import sys

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # KHÔNG bật populate_by_name: nó làm đọc thêm env theo tên trường không tiền tố (LLM_API_KEY…).
        env_ignore_empty=True,  # compose truyền ${X:-} → "" thì dùng mặc định
        extra="ignore",
    )

    llm_base_url: str = Field("", validation_alias="AGENT_LLM_BASE_URL")
    llm_api_key: SecretStr = Field(SecretStr(""), validation_alias="AGENT_LLM_API_KEY")
    llm_model: str = Field("", validation_alias="AGENT_LLM_MODEL")
    llm_temperature: float | None = Field(None, ge=0, le=2, validation_alias="AGENT_LLM_TEMPERATURE")
    llm_timeout_s: float = Field(60, gt=0, validation_alias="AGENT_LLM_TIMEOUT_S")
    llm_max_tokens: int | None = Field(None, gt=0, validation_alias="AGENT_LLM_MAX_TOKENS")

    shared_secret: SecretStr = Field(validation_alias="AGENT_SHARED_SECRET")
    app_internal_url: str = Field("http://family-organizer:3000", validation_alias="APP_INTERNAL_URL")
    version: str = Field("dev", validation_alias="AGENT_VERSION")

    # Giới hạn một lượt (spec §7): timeout cứng, số lượt đồng thời — đầy thì trả 429 ngay.
    run_timeout_s: float = Field(90, gt=0, validation_alias="AGENT_RUN_TIMEOUT_S")
    max_concurrent_runs: int = Field(2, ge=1, validation_alias="AGENT_MAX_CONCURRENT_RUNS")
    max_body_bytes: int = Field(4 * 1024 * 1024, ge=1, validation_alias="AGENT_MAX_BODY_BYTES")

    @field_validator("shared_secret")
    @classmethod
    def _secret_du_dai(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if len(raw) < MIN_SECRET_LEN:
            raise ValueError(f"cần ít nhất {MIN_SECRET_LEN} ký tự")
        # Header đi qua HTTP dạng latin-1 → chỉ nhận ASCII in được, không khoảng trắng hai đầu.
        if not (raw.isascii() and raw.isprintable() and raw.strip() == raw and raw.strip()):
            raise ValueError("chỉ dùng ký tự ASCII in được, không có khoảng trắng ở hai đầu")
        return v

    @property
    def llm_configured(self) -> bool:
        return all(
            s.strip() for s in (self.llm_base_url, self.llm_api_key.get_secret_value(), self.llm_model)
        )


def load_settings() -> Settings:
    """Đọc env; sai thì in lỗi (KHÔNG kèm giá trị — có thể là secret) và thoát."""
    try:
        return Settings()
    except ValidationError as e:
        for err in e.errors(include_input=False, include_url=False):
            name = ".".join(str(x) for x in err["loc"])
            field = Settings.model_fields.get(name)
            env = field.validation_alias if field and isinstance(field.validation_alias, str) else name
            print(f"cấu hình sai: {env}: {err['msg']}", file=sys.stderr)
        raise SystemExit(2) from None
