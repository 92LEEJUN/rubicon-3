# BFF — 클라이언트 표면 게이트웨이 (FastAPI, api-contract §2)
# 실행: uvicorn gateway.main:app --host 0.0.0.0 --port 8000
# 주의: BFF는 BE를 런타임에 import하지 않는다. BE_BASE_URL로 HTTP 중계만 한다.
#       따라서 backend/requirements.txt가 아니라 bff 자체 requirements.txt만 설치한다.
FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 복사·설치 (레이어 캐시) — 런타임 의존성만
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 게이트웨이 코드
COPY gateway/ ./gateway/

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
