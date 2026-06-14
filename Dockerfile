# syntax=docker/dockerfile:1
# S9 딜리버리/DORA(ADR-0065) — 멀티스테이지 backend 컨테이너 릴리스.
# 빌드(deps 설치)와 런(slim·비-root 실행)을 분리하고, OCI 라벨로 버전을 박는다.

# ── stage 1: builder — 빌드 의존성·휠 분리 ───────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build

# 휠 사전 빌드로 런타임 스테이지를 슬림하게 유지.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip wheel --wheel-dir /wheels -r requirements.txt

# ── stage 2: runtime — slim·비-root ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

# 릴리스 버저닝 빌드 인자(scripts/release.py 산출과 연결).
ARG GIT_SHA=unknown
ARG VERSION=unknown
ARG BUILD_DATE=unknown
ARG APP_ENV=prd

# OCI 표준 라벨 — 어떤 커밋/버전이 이 이미지인지 추적(요구사항 4-2).
LABEL org.opencontainers.image.title="rubicon-3-backend" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/92leejun/rubicon-3"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=${APP_ENV} \
    PORT=8000 \
    APP_VERSION=${VERSION} \
    GIT_SHA=${GIT_SHA}

WORKDIR /app

# 휠에서 오프라인 설치(빌드 의존성 미포함 → 슬림).
COPY --from=builder /wheels /wheels
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# 앱 코드 + 런 스크립트.
COPY backend/ ./backend/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# 비-root 실행(요구사항 4-3).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
