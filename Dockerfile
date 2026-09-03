FROM python:3.12-slim

ARG UV_VERSION=0.11.32

ENV KASM_ARTIFACT_DIR=/app/artifacts/release/processed \
    KASM_MODELING_DIR=/app/artifacts/release/modeling \
    PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501

WORKDIR /app

RUN groupadd --system --gid 10001 kasm \
    && useradd --system --uid 10001 --gid kasm --create-home kasm \
    && python -m pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY app ./app
COPY .streamlit ./.streamlit
COPY artifacts/release ./artifacts/release

USER kasm

EXPOSE 8501

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2)"

CMD ["streamlit", "run", "app/streamlit_app.py"]
