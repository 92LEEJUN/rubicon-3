# Backend — 도메인·오케스트레이터 (FastAPI 내부 API, api-contract §2.4)
# 실행: uvicorn app.api.internal:app --host 0.0.0.0 --port 8001
FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 복사·설치 (레이어 캐시)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드
COPY app/ ./app/

EXPOSE 8001

CMD ["uvicorn", "app.api.internal:app", "--host", "0.0.0.0", "--port", "8001"]
