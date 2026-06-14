"""스트림 모듈 임포트 진입점(ADR-0056) — append-only 단일 지점.

각 작업 스트림(관측성·회복력·보안·개인정보·실험 등)은 자기 모듈에서 `wiring.register_*`로 등록하고,
그 모듈이 **로드되도록** 아래에 import 한 줄을 추가한다. `api/internal.py`는 `registry`를 import한 뒤
`wiring.apply(app)`를 호출하므로, 스트림은 **이 파일에 한 줄 append**만 하면 앱 팩토리를 직접 편집하지
않는다(병렬 충돌 회피).

규칙: 한 스트림 = 한 import 줄. 알파벳/추가 순. 부수효과(등록) 목적의 import이므로 noqa.
"""
# 스트림 모듈 import를 여기에 append한다(부수효과=등록). 미사용 import 경고는 줄 끝 noqa로 억제.
# 예) from ..observability import middleware as _obs   # F401 억제 주석을 함께 붙일 것
