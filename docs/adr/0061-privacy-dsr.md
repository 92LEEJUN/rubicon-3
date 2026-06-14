# ADR-0061: 개인정보·DSR(데이터 주체 요청) 스트림

- **상태**: 채택
- **관련**: `docs/production-readiness.md` S5, `docs/adr/0030-consent-scoped.md`(scope 동의),
  `docs/adr/0029-engagement-vs-analytics.md`, `docs/adr/0056-environment-config-baseline.md`(배선 시임),
  `specs/privacy-dsr/`, `backend/app/privacy/*`

## 배경
GDPR·개인정보보호법(PIPA) 대응이 프로덕션 준비도(S5)에서 비어 있다(⬜). 사용자는 기능별 동의를
개별 제어(ADR-0030)할 수 있어야 하고, 데이터 주체로서 **접근/내보내기·삭제·정정** 요청(DSR)을 할 수
있어야 한다. 또한 **보존 기한**(저장 제한)과 **감사 기록**(처리 활동)이 필요하다. 상태 저장소는 이미
`user_id`로 키잉돼 있어(멀티테넌트 준비, ADR-0049), 그 키를 재사용해 데이터를 모으고/지울 수 있다.

## 후보안
| 안 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A | DSR 로직을 `api/internal.py` 앱 팩토리에 직접 추가 | 단순 | 공유 핫스팟 편집(병렬 충돌)·책임 혼재 |
| B | 동의 저장을 User에서 분리한 **별도 ConsentStore 스키마** | 동의 독립 | ADR-0030 모델 중복·마이그레이션 부담 |
| **C (선택)** | **신규 `privacy/` 패키지 + 별도 라우터(`register_router`) + User.consent 유지** | 격리·추가형·핫스팟 미편집 | 라우터가 공유 컨테이너를 lazy import |

## 결정
**C.**
- 신규 패키지 `backend/app/privacy/`에 **ConsentStore·DSRService·RetentionPolicy·AuditLog**를 모은다.
- 엔드포인트는 신규 `APIRouter`(`/internal/privacy/*`)로 만들어 **`wiring.register_router`로 등록**하고,
  `platform/registry.py`에 import 한 줄(append, `# noqa: F401`)을 더해 로드한다(ADR-0056). 앱 팩토리
  `api/internal.py`는 **편집하지 않는다**(병렬 충돌 회피).
- **동의는 `User.consent.scopes`(ADR-0030)에 유지**한다. ConsentStore는 그 위의 scope 부여/철회/조회
  헬퍼일 뿐 새 스키마를 만들지 않는다.
- **DSR은 기존 `user_id` 키잉 Repository를 재사용**한다(시그니처 불변). access/export는 프로필·동의·
  주문·대화 메모리·미해결 스레드·engagement를 모으고, delete는 각 저장소의 삭제 메서드(부재 시 skip)로
  best-effort 삭제한다. rectify는 허용 필드(display_name·addresses·preferences)만 정정한다.
- **보존 스윕은 Mock**(후보 보고·비변형)으로 인터페이스만 제공한다(외부 인프라 어댑터 허용, DoD).
- **감사 훅**은 인메모리 sink로 보안 의미 이벤트(동의 변경·DSR·스윕)를 비차단 기록한다.

## 기각 이유
- **A**: `internal.py`는 공유 핫스팟이라 병렬 스트림이 같은 라인을 편집하면 충돌한다. 등록은 시임으로만.
- **B**: 별도 동의 스키마는 ADR-0030 모델을 중복시키고 마이그레이션을 강제한다. User.consent로 충분하다.

## 결과/영향
- 기본 동작 불변(추가형). 새 엔드포인트는 `/internal/privacy/*`에만 존재하고 기존 계약·시그니처는 그대로다.
- DSR 라우터는 `api/internal.py`의 모듈-수준 `_container`·`_users`를 lazy import로 **공유**한다(상태 일관).
- 실 삭제·실 sink(DB·로그 집계)는 후속 S5/S7 확장에서 retention/audit 어댑터로 배선한다.
- 통합 주의: `platform/registry.py`에 import 한 줄 append, 신규 경로 프리픽스 `/internal/privacy/*`.
