import sys
from pathlib import Path

import pytest

from ritmelli import app
from ritmelli.machine import processes, protected_folder, tasks, update_hook
from ritmelli.machine.installed import UPDATE_TASK
from ritmelli.update import client

HOOK = update_hook.Config("http://127.0.0.1:8765/manifest.json", {1: "key"}, False)


@pytest.fixture
def frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The installed exe in tmp_path, its folder passing the rule, and each task call."""
    calls: list[object] = []

    def disarm(running: str) -> list[str]:
        calls.append(("disarm", running))
        return []

    def delete(name: str, *, end: bool = False) -> None:
        calls.append(("delete", name, end))

    def create(name: str, xml: str, exe: str) -> tuple[int, str]:
        calls.append(("create", name, xml, exe))
        return 0, ""

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ritmelli.exe"))
    monkeypatch.setattr(protected_folder, "unprotected_reason", lambda: None)
    monkeypatch.setattr(tasks, "disarm", disarm)
    monkeypatch.setattr(tasks, "delete", delete)
    monkeypatch.setattr(tasks, "create", create)
    return calls


def test_an_unknown_update_action_exits_with_2() -> None:
    assert app.main(["--atualizador", "xyz"]) == 2


def test_outside_the_frozen_exe_the_round_and_the_task_only_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ritmelli.exe"))
    assert app.main(["--atualizador"]) == 0
    assert app.main(["--atualizador", "tarefa"]) == 0
    assert capsys.readouterr().out.count("only run in the installed executable") == 2
    assert not any(tmp_path.iterdir())


def test_a_folder_that_fails_the_rule_gets_no_task_and_nothing_written(
    frozen: list[object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protected_folder, "unprotected_reason", lambda: "Users write")
    assert app.main(["--atualizador"]) == 1
    assert app.main(["--atualizador", "tarefa"]) == 1
    assert frozen == [("disarm", UPDATE_TASK), ("delete", UPDATE_TASK, True)]
    assert not any(tmp_path.iterdir())


def test_the_round_logs_in_the_app_folder_and_keeps_the_log_before(
    frozen: list[object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "atualizacao"
    folder.mkdir()
    log = folder / "atualizador.log"
    log.write_bytes(b"x" * (app.LOG_MAX + 1))
    monkeypatch.setattr(app, "version", lambda: "0.900.1")
    monkeypatch.setattr(update_hook, "read", lambda: HOOK)

    def run_round(config: client.Config, machine: object) -> None:
        frozen.append((config, machine))
        print("no new version")

    monkeypatch.setattr(client, "run_round", run_round)
    assert app.main(["--atualizador"]) == 0
    assert frozen == [(client.Config("0.900.1", folder, *HOOK), processes)]
    assert log.read_text(encoding="utf-8") == "no new version\n"
    assert (folder / "atualizador.anterior.log").stat().st_size == app.LOG_MAX + 1


def test_the_setup_makes_the_task_run_this_exe_and_the_uninstaller_ends_it(
    frozen: list[object], tmp_path: Path
) -> None:
    assert app.main(["--atualizador", "tarefa"]) == 0
    assert app.main(["--atualizador", "remove"]) == 0
    exe = str(tmp_path / "ritmelli.exe")
    create = ("create", UPDATE_TASK, tasks.UPDATE_XML, exe)
    assert frozen == [create, ("delete", UPDATE_TASK, True)]
