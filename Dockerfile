FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ARG PUID
ARG PGID

RUN groupadd -g ${PGID} iot \
    && useradd -u ${PUID} -g ${PGID} -m iot

USER iot
WORKDIR /home/iot

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# install locked dependencies only; the application code, data and
# resources are volume-mounted at runtime (see docker-compose.yml)
COPY --chown=${PUID}:${PGID} pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--reload", "--log-level", "info", "--host", "0.0.0.0", "--port", "8080", "--root-path", "/epaper"]
