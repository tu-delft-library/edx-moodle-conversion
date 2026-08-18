"""Resolve the development version from Git.

Release builds replace this file with a static release tag.
"""

import subprocess
from pathlib import Path


def _git_version() -> str | None:
    """Return Git's version description, or `None` outside a working tree."""
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
    except (OSError, subprocess.SubprocessError):
        return None


__version__ = _git_version() or "v0.1.0-dev"
