import json
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ritmelli.machine import (
    filter_dll,
    mic_check,
    mic_setup,
    mic_slots,
    protected_folder,
    tasks,
)
from ritmelli.machine.installed import (
    APO_KEY,
    EFX,
    MIC_TASK,
    OUR_CLSIDS,
    SAVED_KEY,
    UPDATE_TASK,
)
from ritmelli.machine.mic_slots_test import EFX_FM, EP, MODES, Registry

UMC_IN = "IN 1-2 (BEHRINGER UMC 404HD 192k)"
UMC_OUT = "OUT 1-2 (BEHRINGER UMC 404HD 192k)"
REALTEK = "Microfone (Realtek(R) Audio)"
ACCENT = "Microfone (Áudio Ação)"


class PC(Registry):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[object, ...]] = []

    def record(self, name: str, answer: object = None) -> Callable[..., Any]:
        def call(*args: object, **kwargs: object) -> object:
            self.calls.append((name, *args, *kwargs.values()))
            return answer

        return call


@pytest.fixture
def pc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PC:
    fake = PC()
    for module in (mic_slots, mic_check, filter_dll):
        monkeypatch.setattr(module, "winreg", fake, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ritmelli.exe"))
    monkeypatch.setattr(protected_folder, "unprotected_reason", lambda: None)
    for module, name, answer in (
        (tasks, "create", (0, "")),
        (tasks, "delete", None),
        (tasks, "exists", False),
        (filter_dll, "place", False),
        (filter_dll, "restart", None),
        (filter_dll, "system32", None),
    ):
        monkeypatch.setattr(module, name, fake.record(name, answer))
    return fake


def test_the_task_comes_first_and_each_device_is_named_once_in_ascii(
    pc: PC, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pc.mic({EFX: EFX_FM})
    silent = [UMC_IN, UMC_OUT, REALTEK, ACCENT]
    summary = f"devices: 5 checked; silent: {'; '.join(silent)}"
    report = mic_check.Report(summary, silent)
    monkeypatch.setattr(mic_check, "after_restart", pc.record("check", report))
    result = tmp_path / "microfone.json"
    assert mic_setup.main(["instala-todos", "--tarefa", "--saida", str(result)]) == 0
    assert result.read_bytes().isascii()
    devices = ["BEHRINGER UMC 404HD 192k", "Realtek(R) Audio", "Áudio Ação"]
    want = {"ok": True, "conferencia": summary, "aparelhos": devices}
    assert json.loads(result.read_bytes()) == want
    exe = str(tmp_path / "ritmelli.exe")
    dll = str(tmp_path / "_internal" / "microfone" / "micfx.dll")
    place = ("place", dll, str(tmp_path / "microfone"))
    create = ("create", MIC_TASK, tasks.MIC_XML, exe)
    assert pc.calls == [create, place, ("restart", False), ("check",)]


def test_the_remove_gives_the_original_back_and_takes_the_rest(
    pc: PC, tmp_path: Path
) -> None:
    before = pc.laptop(MODES)
    mic_slots.put_on(EP)
    mic_check.record([UMC_IN])
    (tmp_path / "microfone").mkdir()
    assert mic_setup.main(["remove"]) == 0
    assert (pc.fx(), pc.values(SAVED_KEY)) == (before, {})
    assert not (tmp_path / "microfone").exists()
    assert pc.calls == [("restart", False), ("delete", MIC_TASK)]


def test_a_folder_that_fails_the_rule_keeps_its_dll_unloaded(
    pc: PC, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protected_folder, "unprotected_reason", lambda: "Users write")
    before = pc.laptop(MODES)
    mic_slots.put_on(EP)
    for clsid in OUR_CLSIDS:
        pc.CreateKeyEx("HKLM", rf"SOFTWARE\Classes\CLSID\{clsid}\InprocServer32")
        pc.CreateKeyEx("HKLM", rf"{APO_KEY}\{clsid}")
    (tmp_path / "microfone").mkdir()
    assert mic_setup.main(["remove"]) == 1
    assert pc.fx() == before
    assert not [path for path in pc.keys if any(c.lower() in path for c in OUR_CLSIDS)]
    assert (tmp_path / "microfone").exists()
    assert pc.calls == [("restart", False), ("delete", MIC_TASK)]


def test_a_folder_that_fails_the_rule_takes_both_tasks_away(
    pc: PC, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(protected_folder, "unprotected_reason", lambda: "Users write")
    before = pc.mic({EFX: EFX_FM})
    result = tmp_path / "microfone.json"
    assert mic_setup.main(["instala-todos", "--saida", str(result)]) == 1
    deleted = [("delete", UPDATE_TASK, True), ("delete", MIC_TASK, False)]
    assert pc.calls == [*deleted, ("exists", UPDATE_TASK), ("exists", MIC_TASK)]
    assert pc.fx() == before
    error = "the app folder isn't protected (Users write): "
    want = {"ok": False, "erro": f"{error}the SYSTEM tasks were removed"}
    assert json.loads(result.read_bytes()) == want


def test_a_check_stuck_in_a_driver_ends_the_process_after_the_result(
    pc: PC, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    held = threading.Event()
    monkeypatch.setattr(mic_check, "run", held.wait)
    monkeypatch.setattr(mic_check, "SETTLE_S", 0)
    monkeypatch.setattr(mic_check, "CHECK_MAX_S", 0.05)
    monkeypatch.setattr(filter_dll, "place", pc.record("place", True))
    monkeypatch.setattr(os, "_exit", pc.record("exit"))
    result = tmp_path / "microfone.json"
    mic_setup.main(["instala-todos", "--saida", str(result)])
    held.set()
    summary = "devices: not checked (still running after 0 s)"
    want: dict[str, object] = {"ok": True, "conferencia": summary, "aparelhos": []}
    assert (json.loads(result.read_bytes()), pc.calls[-1]) == (want, ("exit", 0))
