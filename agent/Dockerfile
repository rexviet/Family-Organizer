# Agent service (Python) — image arm64 cho Pi. Build: docker build --platform linux/arm64 -t family-organizer-agent agent
# Base glibc (python:3.12-slim) vì wheel pydantic-monty là manylinux (spike phase 1).

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Lớp phụ thuộc tách riêng để đổi code không phải tải lại thư viện.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY contracts/operations.schema.json ./contracts/
ARG AGENT_VERSION=dev
ENV PATH=/app/.venv/bin:$PATH \
    AGENT_CONTRACTS_DIR=/app/contracts \
    AGENT_VERSION=$AGENT_VERSION \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 3100
# start-interval: lúc mới khởi động thử dày (3 s) để dịch vụ cập nhật biết agent lên sớm.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --start-interval=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3100/health', timeout=3)"]
CMD ["python", "-m", "family_agent"]
