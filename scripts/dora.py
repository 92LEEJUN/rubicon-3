#!/usr/bin/env python3
"""DORA 메트릭 경량 수집기 (S9 · ADR-0065).

4대 DORA 지표 — 배포빈도·리드타임·변경실패율·MTTR — 를 무거운 인프라 없이
**append-only JSONL** 로 기록하고 집계한다. 워크플로(release.yml)·CLI 가 호출한다.

이벤트 종류:
- deployment : 한 환경으로의 릴리스(선택 commit_date → 리드타임 계산).
- failure    : 배포 후 변경 실패(인시던트 시작).
- recovery   : 인시던트 복구(MTTR 종료).

원칙: stdlib 만(새 의존성 없음). 손상 라인 skip. 이벤트 0건이면 0/null 기본.

사용:
    python scripts/dora.py record deployment --env prd --sha abc1234 --store dora-metrics.jsonl
    python scripts/dora.py record failure --env prd --store dora-metrics.jsonl
    python scripts/dora.py record recovery --env prd --store dora-metrics.jsonl
    python scripts/dora.py report --store dora-metrics.jsonl          # 집계 JSON → stdout
    python scripts/dora.py report --store dora-metrics.jsonl --out build/dora-report.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
EVENTS = ("deployment", "failure", "recovery")
_DEFAULT_STORE = _ROOT / "dora-metrics.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str | None) -> datetime | None:
    if not s or s == "unknown":
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def record(
    event: str,
    *,
    store: Path,
    env: str = "dev",
    sha: str | None = None,
    ts: str | None = None,
    commit_date: str | None = None,
    **extra,
) -> dict:
    """이벤트 한 줄을 JSONL append. 반환: 기록한 dict."""
    if event not in EVENTS:
        raise ValueError(f"unknown event: {event!r} (expected {EVENTS})")
    entry: dict = {"event": event, "ts": ts or _now_iso(), "app_env": env}
    if sha:
        entry["git_sha"] = sha
    if commit_date:
        entry["commit_date"] = commit_date
    entry.update({k: v for k, v in extra.items() if v is not None})
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def load(store: Path) -> list[dict]:
    """JSONL 로드. 누락/빈 파일 → []. 손상 라인 skip."""
    if not store.exists():
        return []
    out: list[dict] = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("event") in EVENTS:
            out.append(obj)
    return out


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 3) if xs else None


def compute(events: list[dict]) -> dict:
    """4대 DORA 지표 집계. 이벤트 0건이면 0/null 기본."""
    deploys = [e for e in events if e["event"] == "deployment"]
    failures = [e for e in events if e["event"] == "failure"]
    recoveries = [e for e in events if e["event"] == "recovery"]

    # 시간순 정렬(ts 기준). 파싱 불가 ts 는 맨 뒤로.
    def _key(e: dict):
        dt = _parse_iso(e.get("ts"))
        return (dt is None, dt or datetime.max.replace(tzinfo=timezone.utc))

    deploy_times = sorted(
        [dt for e in deploys if (dt := _parse_iso(e.get("ts")))]
    )

    # 배포빈도: 총 개수 + 관측 기간(일) 기준 일평균.
    window_days = None
    per_day = None
    if len(deploy_times) >= 2:
        span = (deploy_times[-1] - deploy_times[0]).total_seconds() / 86400.0
        window_days = round(span, 3)
        per_day = round(len(deploy_times) / span, 3) if span > 0 else None
    elif len(deploy_times) == 1:
        window_days = 0.0

    # 리드타임: 각 deployment 의 commit_date → ts (초).
    lead_secs: list[float] = []
    for e in deploys:
        c = _parse_iso(e.get("commit_date"))
        t = _parse_iso(e.get("ts"))
        if c and t and t >= c:
            lead_secs.append((t - c).total_seconds())

    # 변경실패율: failure 수 / deployment 수.
    n_dep = len(deploys)
    cfr = round(len(failures) / n_dep, 3) if n_dep else 0.0

    # MTTR: 각 failure 이후 첫 recovery 까지 (초). 시간순 매칭.
    ordered = sorted(events, key=_key)
    mttr_secs: list[float] = []
    open_fail: datetime | None = None
    for e in ordered:
        dt = _parse_iso(e.get("ts"))
        if e["event"] == "failure" and dt and open_fail is None:
            open_fail = dt
        elif e["event"] == "recovery" and dt and open_fail is not None and dt >= open_fail:
            mttr_secs.append((dt - open_fail).total_seconds())
            open_fail = None

    return {
        "counts": {
            "deployment": n_dep,
            "failure": len(failures),
            "recovery": len(recoveries),
        },
        "deployment_frequency": {
            "total": n_dep,
            "window_days": window_days,
            "per_day": per_day,
        },
        "lead_time_seconds": {"median": _median(lead_secs), "samples": len(lead_secs)},
        "change_failure_rate": cfr,
        "mttr_seconds": {"median": _median(mttr_secs), "samples": len(mttr_secs)},
    }


def _cmd_record(args: argparse.Namespace) -> int:
    entry = record(
        args.event,
        store=Path(args.store).resolve(),
        env=args.env,
        sha=args.sha,
        commit_date=args.commit_date,
    )
    print(f"dora record → {json.dumps(entry, ensure_ascii=False)}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    events = load(Path(args.store).resolve())
    report = compute(events)
    blob = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(blob + "\n", encoding="utf-8")
        print(f"dora report → {out} ({len(events)} events)")
    else:
        print(blob)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DORA 메트릭 수집기(S9·ADR-0065).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("record", help="DORA 이벤트 기록(JSONL append)")
    rp.add_argument("event", choices=EVENTS)
    rp.add_argument("--env", default="dev")
    rp.add_argument("--sha", default=None)
    rp.add_argument("--commit-date", default=None, help="리드타임용 커밋 ISO 시각")
    rp.add_argument("--store", default=str(_DEFAULT_STORE))
    rp.set_defaults(func=_cmd_record)

    pp = sub.add_parser("report", help="4대 지표 집계")
    pp.add_argument("--store", default=str(_DEFAULT_STORE))
    pp.add_argument("--out", default=None, help="출력 JSON 경로(기본 stdout)")
    pp.set_defaults(func=_cmd_report)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
