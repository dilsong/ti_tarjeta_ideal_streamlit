"""Identificador corto de commit/deploy (Render / CI)."""


def deploy_id() -> str:
    """Short git/commit id for Render deploy verification."""
    import os

    for key in ("RENDER_GIT_COMMIT", "SOURCE_VERSION", "GITHUB_SHA", "COMMIT_SHA"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val[:7]
    # fallback: try git
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
