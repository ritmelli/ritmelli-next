from pathlib import Path

import pytest

from ritmelli.update import run_state
from ritmelli.update.client_test import (
    NEW,
    NEXT,
    PID,
    SETUP,
    Fake,
    Served,
    publish,
    run,
)
from ritmelli.update.keys import KEYS


def test_a_manifest_another_key_signed_is_refused(tmp_path: Path) -> None:
    publish()
    state, machine = run(tmp_path, keys=KEYS)
    assert state["estado"] == "parado" and "signature" in str(state["erro"])
    assert "/setup.exe" not in Served.asked and not machine.started


def test_a_setup_with_another_hash_is_not_kept(tmp_path: Path) -> None:
    publish(sha256="0" * 64)
    state, machine = run(tmp_path)
    assert state["estado"] == "parado" and "doesn't match" in str(state["erro"])
    assert not list(tmp_path.glob("Ritmelli-*")) and not machine.started


def test_a_setup_that_changed_after_the_check_does_not_run(tmp_path: Path) -> None:
    setup = tmp_path / "Ritmelli-0.900.2-setup.exe"

    class Swapping(Fake):
        def app_open(self) -> bool:
            setup.write_bytes(SETUP[:-1] + b"X")
            return False

    publish()
    state, machine = run(tmp_path, Swapping())
    assert not machine.started and not setup.exists()
    assert state["estado"] == "parado" and "changed after" in str(state["erro"])


def test_two_setups_that_ended_without_the_version_wait_for_the_next_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_state.write(tmp_path, {"estado": "instalando", "pid": PID, "versao": NEW})
    publish()
    state, machine = run(tmp_path)
    assert state["falhas"] == {NEW: 1} and state["estado"] == "instalando"
    assert "previous install: failed (0.900.2)" in capsys.readouterr().out
    state, _ = run(tmp_path, machine)
    assert state["falhas"] == {NEW: 2} and len(machine.started) == 1
    assert state["estado"] == "parado" and "failed 2 times" in str(state["erro"])
    publish(NEXT)
    state, _ = run(tmp_path, machine)
    assert len(machine.started) == 2 and state["versao"] == NEXT


def test_the_round_never_raises(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    class Broken(Fake):
        def app_open(self) -> bool:
            raise RuntimeError("no process list")

    publish()
    state, _ = run(tmp_path, Broken())
    assert state["estado"] == "parado"
    assert state["erro"] == "RuntimeError: no process list"
    assert "error: RuntimeError: no process list" in capsys.readouterr().out
