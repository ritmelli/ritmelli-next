import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from ritmelli.ports.process.run import run, spawn_detached

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows processes")

PARENT = """
import os, sys
from ritmelli.ports.process.run import spawn_detached
spawn_detached([sys.argv[1], "-c", sys.argv[2], str(os.getpid()), sys.argv[3]])
"""
CHILD = """
import _winapi, pathlib, sys
try:
    parent = _winapi.OpenProcess(_winapi.SYNCHRONIZE, False, int(sys.argv[1]))
except OSError:
    parent = None
if parent is None or _winapi.WaitForSingleObject(parent, 5000) == _winapi.WAIT_OBJECT_0:
    pathlib.Path(sys.argv[2]).touch()
"""


def test_run_returns_the_exit_code_and_the_output() -> None:
    script = "echo out& echo err>&2& exit 3"
    assert run([os.environ["ComSpec"], "/c", script], 5) == (3, "out\nerr\n")


def test_run_refuses_a_program_by_bare_name() -> None:
    with pytest.raises(ValueError, match="full path"):
        run(["cmd.exe", "/c", "exit 0"], 5)


def test_run_kills_a_program_past_its_timeout() -> None:
    ping = Path(os.environ["ComSpec"]).with_name("PING.EXE")
    with pytest.raises(TimeoutError):
        run([str(ping), "-n", "5", "127.0.0.1"], 0.3)


def test_a_detached_program_outlives_its_parent(tmp_path: Path) -> None:
    done = tmp_path / "done"
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    parent = [sys.executable, "-c", PARENT, pythonw, CHILD, str(done)]
    assert run(parent, 5) == (0, "")
    deadline = time.monotonic() + 1.5
    while not done.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert done.exists()


def test_spawn_detached_stays_in_a_job_that_refuses_breakaway(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flags: list[int] = []

    class Popen:
        pid = 7

        def __init__(self, argv: Sequence[str], creationflags: int) -> None:
            flags.append(creationflags)
            if creationflags & subprocess.CREATE_BREAKAWAY_FROM_JOB:
                raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(subprocess, "Popen", Popen)
    assert spawn_detached([r"C:\setup.exe"]) == 7
    detached = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )
    assert flags == [detached | subprocess.CREATE_BREAKAWAY_FROM_JOB, detached]
