"""Single source of truth for the app version.

In CI, build-gui.yml overwrites this whole file with a static assignment
using the pushed release tag right before PyInstaller freezes the binary
(frozen builds have no .git dir to inspect at runtime). For local/dev runs,
resolve it live from git so it always matches the latest tag without
needing a manual bump.
"""

import subprocess
from pathlib import Path


def _git_version() -> str | None:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return None


__version__ = _git_version() or "v0.1.0-dev"
