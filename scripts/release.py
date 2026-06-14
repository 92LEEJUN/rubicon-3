#!/usr/bin/env python3
"""릴리스 버전 스탬프 (S9 · ADR-0065) — 빌드↔릴리스↔런 경계의 '릴리스' 산출물.

빌드(코드→아티팩트)와 런(실행) 사이의 **릴리스 = 빌드 + 구성(버전 스탬프)** 를 만든다.
git sha·빌드 날짜(UTC)·APP_ENV 를 담은 불변 스탬프를 결정적으로 생성해
`build/VERSION`(사람용 한 줄)·`build/version.json`(기계용)으로 떨군다.

원칙:
- 결정적·테스트 가능: sha/now 를 인자로 주입할 수 있어 단위 테스트가 시간/플랫폼에 의존하지 않는다.
- 견고: git 메타를 읽을 수 없으면(얕은 클론·비-git) 실패하지 않고 'unknown' 폴백.
- 새 무거운 의존성 없음(stdlib + git CLI 만).

사용:
    python scripts/release.py stamp --env stg                # build/ 에 VERSION·version.json
    python scripts/release.py stamp --env prd --out dist
    python scripts/release.py stamp --env dev --print        # stdout 으로 JSON 만 출력
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
ENVS = ("dev", "stg", "prd")
_UNKNOWN = "unknown"


def _git(*args: str) -> str | None:
    """git 명령 실행 — 성공 시 stripped stdout, 실패/부재 시 None."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def git_meta() -> dict:
    """git sha(short/full)·커밋 ISO 시각. 읽을 수 없으면 'unknown' 폴백."""
    sha_full = _git("rev-parse", "HEAD") or _UNKNOWN
    sha_short = _git("rev-parse", "--short", "HEAD") or (
        sha_full[:7] if sha_full != _UNKNOWN else _UNKNOWN
    )
    commit_date = _git("show", "-s", "--format=%cI", "HEAD") or _UNKNOWN
    return {"git_sha": sha_short, "git_sha_full": sha_full, "commit_date": commit_date}


def _norm_env(env: str | None) -> str:
    e = (env or "dev").strip().lower()
    return e if e in ENVS else "dev"


def build_stamp(
    env: str | None,
    *,
    meta: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """결정적 버전 스탬프 생성. meta/now 주입 가능(테스트 결정성)."""
    app_env = _norm_env(env)
    m = meta if meta is not None else git_meta()
    ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    build_date = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_tag = ts.strftime("%Y.%m.%d")
    sha = m.get("git_sha", _UNKNOWN)
    version = f"{date_tag}+{sha}.{app_env}"
    return {
        "version": version,
        "app_env": app_env,
        "git_sha": sha,
        "git_sha_full": m.get("git_sha_full", _UNKNOWN),
        "build_date": build_date,
        "commit_date": m.get("commit_date", _UNKNOWN),
    }


def version_string(stamp: dict) -> str:
    """사람용 VERSION 한 줄."""
    return str(stamp["version"])


def write(stamp: dict, out_dir: Path) -> tuple[Path, Path]:
    """build/VERSION(텍스트) + build/version.json(기계) 둘 다 기록. 반환: (txt, json)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    txt = out_dir / "VERSION"
    js = out_dir / "version.json"
    txt.write_text(version_string(stamp) + "\n", encoding="utf-8")
    js.write_text(json.dumps(stamp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return txt, js


def _cmd_stamp(args: argparse.Namespace) -> int:
    stamp = build_stamp(args.env)
    if args.print:
        print(json.dumps(stamp, ensure_ascii=False))
        return 0
    out_dir = Path(args.out).resolve()
    txt, js = write(stamp, out_dir)
    print(f"release stamp → {version_string(stamp)}")
    print(f"  VERSION  → {txt}")
    print(f"  version.json → {js}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="릴리스 버전 스탬프 생성(S9·ADR-0065).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("stamp", help="버전 스탬프 생성")
    sp.add_argument("--env", default="dev", help="대상 환경(dev/stg/prd)")
    sp.add_argument("--out", default=str(_ROOT / "build"), help="출력 디렉터리(기본 build/)")
    sp.add_argument("--print", action="store_true", help="파일 대신 stdout 으로 JSON 출력")
    sp.set_defaults(func=_cmd_stamp)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
