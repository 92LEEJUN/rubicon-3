# 작업 (Tasks) — S9 딜리버리/DORA

> `design.md` 를 구현으로 나눈 체크리스트. 끝에 관련 요구사항 번호 표기.

## 작업 목록

- [x] 1. ADR-0065 작성 + 인덱스 참조 _(요구사항 1~4)_
  - `docs/adr/0065-delivery-dora.md` (README 인덱스는 main 머지 시 갱신 — 편집 금지 대상)
- [x] 2. 스펙 3종 _(요구사항 1~4)_
  - requirements / design / tasks
- [x] 3. `scripts/release.py` — 버전 스탬프 _(요구사항 1)_
  - [x] 3.1 git_meta 폴백
  - [x] 3.2 build_stamp/version_string(결정적)
  - [x] 3.3 write(VERSION + version.json), CLI `stamp`
- [x] 4. `scripts/dora.py` — DORA 수집기 _(요구사항 2)_
  - [x] 4.1 record(JSONL append) / load
  - [x] 4.2 compute(4지표) / CLI `record`·`report`
- [x] 5. `.github/workflows/release.yml` — 환경 인지 배포 + 게이트 + DORA 기록 _(요구사항 3)_
- [x] 6. `ci.yml` 추가형 `release-dry-run` 잡(기존 잡 불변) _(요구사항 3-4)_
- [x] 7. 컨테이너 릴리스 _(요구사항 4)_
  - [x] 7.1 멀티스테이지 `Dockerfile`(비-root·OCI 라벨)
  - [x] 7.2 `docker/entrypoint.sh`·`.dockerignore`
  - [x] 7.3 `docker-compose.yml`(APP_ENV·포트·healthcheck)
- [x] 8. 테스트 `backend/tests/test_release.py`(release + dora) _(요구사항 1, 2)_
- [x] 9. 검증: ruff·pytest·스크립트 실행·YAML 문법

## 진행 메모
- 워크트리에서 작업 후 `feat/delivery-dora`로 푸시. PR은 열지 않음.
- `docs/production-readiness.md`·`docs/adr/README.md`·`.github/workflows/security.yml` 미편집(금지).
- 새 무거운 의존성 없음(stdlib만). `pyyaml`은 CI/검증용으로만 사용(워크플로 파싱), 런타임 의존성 아님.
