#!/usr/bin/env sh
# S9 딜리버리/DORA(ADR-0065) — '런' 단계 엔트리포인트.
# 빌드(이미지)·릴리스(버전 라벨)와 분리된 실행 단계. APP_ENV·PORT 인지.
set -eu

APP_ENV="${APP_ENV:-prd}"
PORT="${PORT:-8000}"
APP_VERSION="${APP_VERSION:-unknown}"
GIT_SHA="${GIT_SHA:-unknown}"

echo "[entrypoint] run stage — env=${APP_ENV} version=${APP_VERSION} sha=${GIT_SHA} port=${PORT}"

# 인자가 주어지면 그대로 실행(디버그·일회성 명령), 아니면 uvicorn 기동.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec uvicorn app.api.internal:app --host 0.0.0.0 --port "${PORT}"
