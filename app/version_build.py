"""Identificador corto de commit/deploy (Render / CI / Docker build)."""

from __future__ import annotations

from pathlib import Path

_BUILD_FILE = Path(__file__).resolve().parent / "build_id.txt"


def deploy_id() -> str:
    """Short git/commit id for Render deploy verification."""
    import os

    for key in ("RENDER_GIT_COMMIT", "SOURCE_VERSION", "GITHUB_SHA", "COMMIT_SHA", "TI_BUILD_ID"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val[:7]

    if _BUILD_FILE.is_file():
        try:
            baked = _BUILD_FILE.read_text(encoding="utf-8").strip()
            if baked:
                return baked[:7]
        except OSError:
            pass

    try:
        import subprocess

        out = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            return out
    except Exception:
        pass
    return "unknown"
