import argparse
import json
import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from ritmelli.machine import filter_dll, mic_check, mic_slots, protected_folder, tasks
from ritmelli.machine.installed import MIC_ACTIONS, MIC_MODE, MIC_TASK


class Failed(Exception):
    def __init__(self, error: str, report: mic_check.Report | None = None) -> None:
        super().__init__(error)
        self.report = report


def _device_of(name: str) -> str:
    if not name.endswith(")"):
        return name
    depth = 0
    for i in range(len(name) - 1, 0, -1):
        depth += {")": 1, "(": -1}.get(name[i], 0)
        if depth == 0:
            return name[i + 1 : -1]
    return name


def _put_on_all() -> mic_check.Report | None:
    app = Path(sys.executable).parent
    dll = app / "_internal" / "microfone" / "micfx.dll"
    replaced = filter_dll.place(str(dll), str(app / "microfone"))
    changed = 0
    failures: list[str] = []
    for endpoint, name, device in mic_slots.microphones():
        try:
            if mic_slots.put_on(endpoint):
                changed += 1
        except mic_slots.LeftOut:
            continue
        except OSError as error:
            failures.append(
                f"the filter wasn't installed on {name} ({device}): {error}"
            )
    if changed or replaced:
        if restart_error := filter_dll.restart(only_service=not changed):
            failures.append(restart_error)
    report = mic_check.after_restart() if changed or replaced else None
    if failures:
        raise Failed("; ".join(failures), report)
    return report


def _install(task: bool) -> mic_check.Report | None:
    if reason := protected_folder.unprotected_reason():
        errors = "; ".join(tasks.disarm(MIC_TASK)) or "the SYSTEM tasks were removed"
        raise Failed(f"the app folder isn't protected ({reason}): {errors}")
    if task:
        code, out = tasks.create(MIC_TASK, tasks.MIC_XML, sys.executable)
        if code:
            raise Failed(f"couldn't create the task ({code}): {out.strip()}")
    return _put_on_all()


def _forget(folder: Path, protected: bool) -> None:
    if protected:
        shutil.rmtree(folder, ignore_errors=True)
    tasks.delete(MIC_TASK)
    mic_slots.forget_hosts()
    filter_dll.forget()
    mic_check.record([])


def _remove() -> None:
    changed = False
    for endpoint, _, _ in mic_slots.microphones():
        changed |= mic_slots.give_back(endpoint)
    left = any(mic_slots.has_filter(mic[0]) for mic in mic_slots.microphones())
    reason = protected_folder.unprotected_reason()
    folder = Path(sys.executable).with_name("microfone")
    if not left:
        mic_slots.remove_com()
    try:
        error = filter_dll.restart(only_service=False) if changed else None
    finally:
        if not left:
            _forget(folder, protected=not reason)
    if reason:
        restored = f"the microphones were restored, and {folder} was left as it is"
        raise Failed(f"the app folder isn't protected ({reason}): {restored}")
    if error:
        raise Failed(error)


def _write(path: str, result: dict[str, object]) -> None:
    partial = Path(f"{path}.partial")
    try:
        partial.write_text(json.dumps(result), encoding="ascii")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def _change(action: str, task: bool, result_file: str | None) -> int:
    install, _ = MIC_ACTIONS
    result: dict[str, object] = {"ok": True}
    report = None
    try:
        report = _install(task) if action == install else _remove()
    except Failed as failed:
        result = {"ok": False, "erro": str(failed)}
        report = failed.report
    except Exception as error:
        result = {"ok": False, "erro": f"{type(error).__name__}: {error}"}
    if report is not None:
        result["conferencia"] = report.summary
        result["aparelhos"] = list(dict.fromkeys(map(_device_of, report.silent)))
    code = 1
    try:
        if result_file:
            _write(result_file, result)
        code = 0 if result["ok"] else 1
    finally:
        if report is not None and report.stuck:
            os._exit(code)
    return code


def main(args: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog=MIC_MODE)
    parser.add_argument("action", choices=(*MIC_ACTIONS, "estado", "confere"))
    parser.add_argument("--tarefa", action="store_true")
    parser.add_argument("--saida")
    options = parser.parse_args(args)
    if options.action == "confere":
        print(json.dumps(mic_check.run()))
    elif options.action == "estado":
        for endpoint, name, device in mic_slots.microphones(active_only=True):
            mark = "filter" if mic_slots.has_filter(endpoint) else "no filter"
            print(f"{name} ({device}) {endpoint}: {mark}")
    elif not getattr(sys, "frozen", False):
        print("the mic setup only runs in the installed executable")
    else:
        return _change(options.action, options.tarefa, options.saida)
    return 0
