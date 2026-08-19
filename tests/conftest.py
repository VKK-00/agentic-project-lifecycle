"""Portable test setup for OS-isolation-dependent integration tests."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


_SHIM_DIR: Path | None = None
_ORIGINAL_PATH: str | None = None


def _linux_unshare_supported() -> bool:
    executable = shutil.which("unshare")
    if sys.platform != "linux" or not executable:
        return False
    result = subprocess.run(
        [
            executable,
            "--net",
            "--pid",
            "--fork",
            "--kill-child=SIGKILL",
            "--map-root-user",
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    return result.returncode == 0


def pytest_configure() -> None:
    """Install a process-supervising test shim when the host blocks unshare.

    The shim is intentionally limited to the test process environment. The
    production default remains fail-closed and still requires a real supported
    OS isolator.
    """

    global _ORIGINAL_PATH, _SHIM_DIR
    if sys.platform != "linux" or _linux_unshare_supported():
        return
    source = Path(__file__).resolve().parent / "support" / "fake_unshare.py"
    _SHIM_DIR = Path(tempfile.mkdtemp(prefix="apl-test-isolator-"))
    target = _SHIM_DIR / "unshare"
    shutil.copy2(source, target)
    target.chmod(0o700)
    _ORIGINAL_PATH = os.environ.get("PATH", "")
    os.environ["PATH"] = str(_SHIM_DIR) + os.pathsep + _ORIGINAL_PATH
    os.environ["APL_TEST_FAKE_UNSHARE"] = "1"


def pytest_unconfigure() -> None:
    global _ORIGINAL_PATH, _SHIM_DIR
    if _ORIGINAL_PATH is not None:
        os.environ["PATH"] = _ORIGINAL_PATH
    os.environ.pop("APL_TEST_FAKE_UNSHARE", None)
    if _SHIM_DIR is not None:
        shutil.rmtree(_SHIM_DIR, ignore_errors=True)
