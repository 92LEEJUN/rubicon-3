# 작업 (Tasks) — FE 모션·디자인 폴리시

> `design.md` 구현 체크리스트.

- [x] 1. ADR-0068 + 인덱스 _(요구사항 1~4)_
- [x] 2. `design/motion.ts` — duration·easing·spring·distance·variants 토큰 _(요구사항 1-1)_
- [x] 3. `components/motion.tsx` — `MotionView`·`FadeInView`·`Stagger`/`StaggerItem`·`PressableScale`·reduced-motion _(요구사항 1-2·4-1)_
- [x] 4. `components/Skeleton.tsx` — 시머 박스 + `SkeletonCard` _(요구사항 3-1)_
- [x] 5. 프리미티브 폴리시 — `Card`(elevation·press)·`Button`(스프링 누름) + `shadow.elevated` 토큰 _(요구사항 2-1·2-3)_
- [x] 6. 홈 적용 — 타일 `Stagger`+`PressableScale`·브리핑/추천 누름·`FadeInView` _(요구사항 2·3-1)_
- [x] 7. 배너 `AnimatePresence` enter/exit(slideInDown) + 채팅 섹션 `FadeInView` 등장 _(요구사항 3-2·3-3)_
- [x] 8. 검증 — `tests/motion.test.tsx`(6) + 전 jest 스위트(114) + `vite build` green _(요구사항 4-2)_

## 후속(별도 라운드)
- [ ] 전역 전환(탭 스위치·패널 open/close 트랜지션) _(요구사항 3-2 확장)_
- [ ] 디테일 패스 — 타이포 위계·간격 리듬·빈/에러 상태 4종(frontend-architecture §6)

## 진행 메모
- 엔진=framer-motion(`motion.create(View)`), 순수 웹 타깃. reduced-motion 존중. 계약·데이터 흐름 무변경.
