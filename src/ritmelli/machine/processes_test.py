import os
import shutil
import signal
import sys
from pathlib import Path

import pytest

from ritmelli.machine import processes
from ritmelli.ports.process.run import spawn_detached

windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows processes")


@windows
def test_the_list_finds_this_process() -> None:
    assert processes.alive(os.getpid())


@windows
def test_a_ritmelli_exe_of_the_folder_counts_as_open(tmp_path: Path) -> None:
    app, other = tmp_path / "app", tmp_path / "other"
    app.mkdir()
    other.mkdir()
    ping = Path(os.environ["ComSpec"]).with_name("PING.EXE")
    fake = shutil.copy(ping, app / "ritmelli.exe")
    pid = spawn_detached([str(fake), "-n", "30", "127.0.0.1"])
    try:
        assert processes.app_open(str(app))
        assert not processes.app_open(str(other))
    finally:
        os.kill(pid, signal.SIGTERM)


def test_this_process_does_not_count_and_one_it_cannot_look_at_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreadable(pid: int) -> None:
        return None

    mine = [(os.getpid(), "ritmelli.exe"), (8, "Ritmelli.EXE")]
    monkeypatch.setattr(processes, "_processes", lambda: mine[:1])
    assert not processes.app_open("app")
    monkeypatch.setattr(processes, "_processes", lambda: mine)
    monkeypatch.setattr(processes, "_image", unreadable)
    assert processes.app_open("app")
