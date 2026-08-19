#!/usr/bin/env python3
"""Test-only stand-in for ``unshare`` on hosts that disable user namespaces.

It preserves the process-supervision semantics used by the test suite but does
not claim to provide network isolation. Production code never selects this
helper; ``tests/conftest.py`` places it on PATH only when the real Linux
isolator fails an explicit capability probe.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def _command(argv: list[str]) -> list[str]:
    try:
        separator = argv.index("--")
    except ValueError as exc:
        raise SystemExit("fake unshare requires a '--' command separator") from exc
    command = argv[separator + 1 :]
    if not command:
        raise SystemExit("fake unshare requires a command after '--'")
    return command


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=0.2)
            return
        except subprocess.TimeoutExpired:
            continue


def main() -> int:
    command = _command(sys.argv[1:])
    if (
        os.environ.get("APL_TEST_FAKE_UNSHARE") == "1"
        and os.environ.get("APL_NETWORK_ISOLATION_PROBE") == "1"
    ):
        # Report a distinct synthetic namespace only to the explicit capability
        # probe. Ordinary verification commands still run under process-group
        # supervision without claiming real network isolation.
        print("net:[apl-test-isolated]")
        return 0
    process = subprocess.Popen(command, start_new_session=True)

    def forward(signum: int, _frame: object) -> None:
        _terminate_group(process)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    returncode = process.wait()
    # The leader may have exited after starting descendants. Mimic
    # ``unshare --kill-child`` by terminating the entire nested process group.
    _terminate_group(process)
    # Give the kernel a short scheduling opportunity to reap group members
    # before the wrapper closes inherited output descriptors.
    time.sleep(0.01)
    return int(returncode)


if __name__ == "__main__":
    raise SystemExit(main())
