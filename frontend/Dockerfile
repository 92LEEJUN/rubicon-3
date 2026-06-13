# Frontend — RN(Web) 앱. 멀티스테이지: vite 빌드 → nginx 정적 서빙.
# base는 "/" (DEPLOY_BASE 미지정). FE는 BFF만 호출하며 접속 주소는
# 브라우저 query param(?api/?ws)으로 주입한다(compose.yml 참고).

# --- build stage ---
FROM node:20-slim AS build
WORKDIR /app

# 의존성 먼저 (레이어 캐시)
COPY package.json package-lock.json ./
RUN npm ci

# 소스 복사 후 빌드 (base "/" — DEPLOY_BASE 미설정)
COPY . .
RUN npm run build

# --- serve stage ---
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
