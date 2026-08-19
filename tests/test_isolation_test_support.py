from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
FAKE_UNSHARE = ROOT / "tests" / "support" / "fake_unshare.py"


def test_fake_unshare_executes_command_after_separator() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(FAKE_UNSHARE),
            "--net",
            "--pid",
            "--fork",
            "--kill-child=SIGKILL",
            "--map-root-user",
            "--",
            sys.executable,
            "-c",
            "print('isolated-test-command')",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "isolated-test-command"


def test_fake_unshare_terminates_background_descendants(tmp_path: Path) -> None:
    marker = tmp_path / "orphan.txt"
    child = (
        "import time; from pathlib import Path; "
        f"time.sleep(0.4); Path({str(marker)!r}).write_text('escaped')"
    )
    parent = (
        "import subprocess,sys; "
        f"subprocess.Popen([sys.executable,'-c',{child!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL)"
    )
    result = subprocess.run(
        [
            sys.executable,
            str(FAKE_UNSHARE),
            "--pid",
            "--fork",
            "--kill-child=SIGKILL",
            "--map-root-user",
            "--",
            sys.executable,
            "-c",
            parent,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    time.sleep(0.6)

    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()
