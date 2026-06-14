"""S9 딜리버리/DORA(ADR-0065) — release.py · dora.py 단위 테스트(결정적).

루트 `scripts/` 를 import 경로에 추가해 빌드·릴리스·운영 레이어 스크립트만 검증한다.
앱 런타임 의존성 없음(stdlib 만).
"""
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_s9_{name}", _SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


release = _load("release")
dora = _load("dora")


# ── release: 버전 스탬프 ─────────────────────────────────────────────────────
def test_build_stamp_deterministic():
    """meta/now 주입 시 스탬프가 결정적(요구사항 1-1)."""
    meta = {"git_sha": "abc1234", "git_sha_full": "abc1234ff", "commit_date": "2026-06-14T00:00:00Z"}
    now = datetime(2026, 6, 14, 12, 30, 0, tzinfo=timezone.utc)
    s = release.build_stamp("stg", meta=meta, now=now)
    assert s["app_env"] == "stg"
    assert s["git_sha"] == "abc1234"
    assert s["build_date"] == "2026-06-14T12:30:00Z"
    assert s["version"] == "2026.06.14+abc1234.stg"
    # 동일 입력 → 동일 출력.
    assert release.build_stamp("stg", meta=meta, now=now) == s


def test_unknown_env_falls_back_to_dev():
    """미지 env → dev 폴백(요구사항 1, config 규약 정합)."""
    s = release.build_stamp("qa", meta={}, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert s["app_env"] == "dev"


def test_missing_git_meta_uses_unknown():
    """git 메타 부재 → 'unknown' 폴백(요구사항 1-3)."""
    s = release.build_stamp("prd", meta={}, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert s["git_sha"] == "unknown"
    assert s["git_sha_full"] == "unknown"
    assert s["commit_date"] == "unknown"
    assert s["version"].endswith("+unknown.prd")


def test_write_emits_version_and_json(tmp_path):
    """VERSION(텍스트) + version.json(기계) 둘 다 기록(요구사항 1-2)."""
    meta = {"git_sha": "deadbee", "git_sha_full": "deadbeef", "commit_date": "unknown"}
    s = release.build_stamp("dev", meta=meta, now=datetime(2026, 6, 14, tzinfo=timezone.utc))
    txt, js = release.write(s, tmp_path)
    assert txt.read_text(encoding="utf-8").strip() == s["version"]
    loaded = json.loads(js.read_text(encoding="utf-8"))
    assert loaded == s


def test_release_cli_print(capsys):
    """CLI stamp --print 가 JSON 한 줄을 stdout 으로(스크립트 실행 경로)."""
    rc = release.main(["stamp", "--env", "dev", "--print"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    obj = json.loads(out)
    assert obj["app_env"] == "dev" and "version" in obj


# ── dora: 수집·집계 ──────────────────────────────────────────────────────────
def test_dora_record_load_roundtrip(tmp_path):
    """record → load round-trip(요구사항 2-1)."""
    store = tmp_path / "m.jsonl"
    dora.record("deployment", store=store, env="prd", sha="abc", ts="2026-06-14T00:00:00Z")
    dora.record("failure", store=store, env="prd", ts="2026-06-14T01:00:00Z")
    events = dora.load(store)
    assert [e["event"] for e in events] == ["deployment", "failure"]
    assert events[0]["git_sha"] == "abc"


def test_dora_record_rejects_unknown_event(tmp_path):
    store = tmp_path / "m.jsonl"
    try:
        dora.record("explode", store=store)
    except ValueError:
        return
    raise AssertionError("unknown event should raise ValueError")


def test_dora_load_skips_corrupt_lines(tmp_path):
    """손상/비-DORA 라인 skip(견고성)."""
    store = tmp_path / "m.jsonl"
    store.write_text(
        '{"event":"deployment","ts":"2026-06-14T00:00:00Z"}\n'
        "not-json\n"
        '{"event":"noise"}\n'
        '\n',
        encoding="utf-8",
    )
    events = dora.load(store)
    assert len(events) == 1 and events[0]["event"] == "deployment"


def test_dora_compute_empty_defaults():
    """이벤트 0건 → 0/null 기본(요구사항 2-3)."""
    r = dora.compute([])
    assert r["counts"] == {"deployment": 0, "failure": 0, "recovery": 0}
    assert r["change_failure_rate"] == 0.0
    assert r["deployment_frequency"]["total"] == 0
    assert r["lead_time_seconds"]["median"] is None
    assert r["mttr_seconds"]["median"] is None


def test_dora_compute_four_metrics():
    """배포빈도·리드타임·CFR·MTTR 계산(요구사항 2-2)."""
    events = [
        # deployment 2건(2일 간격) + 리드타임(commit→ts).
        {"event": "deployment", "ts": "2026-06-10T00:00:00Z", "commit_date": "2026-06-09T23:00:00Z"},
        {"event": "deployment", "ts": "2026-06-12T00:00:00Z", "commit_date": "2026-06-11T22:00:00Z"},
        # failure 1건 → recovery 1건(2시간 후) = MTTR.
        {"event": "failure", "ts": "2026-06-12T01:00:00Z"},
        {"event": "recovery", "ts": "2026-06-12T03:00:00Z"},
    ]
    r = dora.compute(events)
    assert r["counts"] == {"deployment": 2, "failure": 1, "recovery": 1}
    # 배포빈도: 2건 / 2일 = 1.0/day.
    assert r["deployment_frequency"]["window_days"] == 2.0
    assert r["deployment_frequency"]["per_day"] == 1.0
    # 리드타임 중앙값: 1h + 2h → median = 1.5h = 5400s.
    assert r["lead_time_seconds"]["samples"] == 2
    assert r["lead_time_seconds"]["median"] == 5400.0
    # CFR: 1 failure / 2 deployment = 0.5.
    assert r["change_failure_rate"] == 0.5
    # MTTR: 2h = 7200s.
    assert r["mttr_seconds"]["median"] == 7200.0


def test_dora_report_cli_stdout(tmp_path, capsys):
    """report CLI 가 집계 JSON 을 stdout 으로(스크립트 실행 경로)."""
    store = tmp_path / "m.jsonl"
    dora.record("deployment", store=store, env="stg", ts="2026-06-14T00:00:00Z")
    rc = dora.main(["report", "--store", str(store)])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"]["deployment"] == 1
