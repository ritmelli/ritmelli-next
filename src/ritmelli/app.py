"""The entry point of ritmelli.exe. The first argument picks a mode from MODES.

With no argument the exe exits with 0 at once, with no window and nothing written.
That is what the shortcut and the end of the setup run, and there is no screen yet.
A first argument that is not in MODES exits with 2 at once. The uninstaller waits
for each line an old setup left in its log, so an argument this exe does not know
must never open the app.
"""

import contextlib
import json
import pkgutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import ritmelli
from ritmelli.machine import mic_setup, processes, protected_folder, tasks, update_hook
from ritmelli.machine.installed import (
    MIC_MODE,
    UPDATE_ACTIONS,
    UPDATE_MODE,
    UPDATE_TASK,
)
from ritmelli.update import client, keys, manifest

UNKNOWN = 2
LOG_MAX = 1 << 20


def version() -> str:
    """The version the build gave, from the file the recipe puts next to this script."""
    return Path(__file__).with_name("version.txt").read_text(encoding="ascii")


def describe(args: Sequence[str]) -> int:
    """Writes what this exe is to the file in args: the exe has no console. The
    modules are those of the package inside the exe, found by folder as the kernel
    will find its commands. A build that froze only what app.py imports lists fewer,
    and build_info.py refuses it."""
    if len(args) != 1:
        return UNKNOWN
    found = pkgutil.walk_packages(ritmelli.__path__, "ritmelli.")
    limits = {
        "manifest": manifest.MANIFEST_MAX,
        "signature": manifest.SIGNATURE_MAX,
        "setup": manifest.SETUP_MAX,
    }
    updater = {
        "manifest_url": keys.MANIFEST_URL,
        "keys": keys.KEYS,
        "apps": [manifest.APP],
        "limits": limits,
    }
    described = {
        "version": version(),
        "modes": sorted(MODES),
        "modules": sorted(module.name for module in found),
        "updater": updater,
    }
    Path(args[0]).write_text(json.dumps(described), encoding="utf-8")
    return 0


def update(args: Sequence[str]) -> int:
    """Alone, the round of the update task. The setup runs tarefa, which creates the
    task, and the uninstaller runs remove, which ends and deletes it."""
    action = args[0] if args else None
    create, remove = UPDATE_ACTIONS
    if action == remove:
        tasks.delete(UPDATE_TASK, end=True)
        return 0
    if action not in (None, create):
        print(f"unknown mode: {action}")
        return UNKNOWN
    if not getattr(sys, "frozen", False):
        print("the update task and its round only run in the installed executable")
        return 0
    return _round() if action is None else _create_task()


def _round() -> int:
    """The round runs as SYSTEM the setup it downloads into the app folder, so the
    folder must pass the protected folder rule before anything is written there.
    Failed, both SYSTEM tasks go, and only a full setup makes them again."""
    if reason := protected_folder.unprotected_reason():
        errors = tasks.disarm(UPDATE_TASK)
        print(f"the app folder isn't protected: {reason}", *errors, sep="\n")
        return 1
    folder = Path(sys.executable).with_name("atualizacao")
    folder.mkdir(exist_ok=True)
    log = folder / "atualizador.log"
    with contextlib.suppress(OSError):
        if log.stat().st_size > LOG_MAX:
            log.replace(log.with_name("atualizador.anterior.log"))
    config = client.Config(version(), folder, *update_hook.read())
    with log.open("a", encoding="utf-8") as out, contextlib.redirect_stdout(out):
        client.run_round(config, processes)
    return 0


def _create_task() -> int:
    if reason := protected_folder.unprotected_reason():
        tasks.delete(UPDATE_TASK, end=True)
        print(f"no update task: the app folder isn't protected: {reason}")
        return 1
    code, out = tasks.create(UPDATE_TASK, tasks.UPDATE_XML, sys.executable)
    if code:
        print(f"couldn't create the update task ({code}): {out.strip()}")
    return code


MODES: dict[str, Callable[[Sequence[str]], int]] = {
    "--describe": describe,
    UPDATE_MODE: update,
    MIC_MODE: mic_setup.main,
}


def main(argv: Sequence[str]) -> int:
    if not argv:
        return 0
    mode = MODES.get(argv[0])
    return UNKNOWN if mode is None else mode(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
