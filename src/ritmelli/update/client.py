"""The round of the update task, as v0.7.0 runs it: ritmelli.exe --atualizador, as
SYSTEM, at logon and every 4 hours. The setup goes into the app folder, where only
administrators write, and is checked again right before it starts: checked earlier, a
program could swap it in the middle. app.py checks the protected folder first and
gives the round the Windows side."""

import contextlib
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from ritmelli.update import download, run_state
from ritmelli.update.manifest import MANIFEST_MAX, SIGNATURE_MAX, Manifest
from ritmelli.update.manifest import check, parse_version
from ritmelli.update.verify import Refused

# Ritmelli asks for a round as it closes, so it may still be closing.
CLOSE_WAIT_S = 20.0
# Setups of one version that ended without it. After that, only a newer version.
SETUP_TRIES = 2
# No /reabrir: run as SYSTEM, the setup would open Ritmelli as SYSTEM.
SETUP_ARGS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
# The name v0.7.0 gives a download cut in the middle. Its clean-up deletes it.
DOWNLOADING = ".baixando"


@dataclass(frozen=True)
class Config:
    """The version of this exe, its {app}\\atualizacao folder, and the manifest
    address, the keys and https_only, from the hook when it has them."""

    version: str
    folder: Path
    manifest_url: str
    keys: Mapping[int, str]
    https_only: bool


class Machine(Protocol):
    """Whether a ritmelli.exe of the app folder runs, other than this one; whether a
    pid runs; and a setup started detached, by its pid."""

    def app_open(self) -> bool: ...
    def alive(self, pid: int) -> bool: ...
    def launch(self, argv: Sequence[str]) -> int: ...


def run_round(config: Config, machine: Machine) -> None:
    """One round. It never raises: an error stops it as parado, with the reason."""
    try:
        _round(config, machine)
    except Exception as error:
        reason = f"{type(error).__name__}: {error}"
        _log(f"error: {reason}")
        run_state.write(config.folder, {"estado": "parado", "erro": reason})


def _round(config: Config, machine: Machine) -> None:
    _settle(config, machine)
    _clean(config)
    found = _wanted(config)
    if found is None:
        return
    try:
        setup = _download(config, found)
    except (OSError, ValueError) as error:
        text = str(error)
        _write(config, f"download: {text}", estado="parado", progresso=0.0, erro=text)
        return
    line, sha = f"{setup.name} downloaded and checked", found.installer.sha256
    _write(config, line, estado="pronta", progresso=1.0, setup=setup.name, sha256=sha)
    deadline = time.monotonic() + CLOSE_WAIT_S
    while machine.app_open():
        if time.monotonic() >= deadline:
            _log("Ritmelli is open: the new version goes in when it closes")
            return
        time.sleep(1.0)
    _install(config, machine, setup, found)


def _settle(config: Config, machine: Machine) -> None:
    """The setup the round before started has exited. This exe is its version, or the
    setup failed and that counts."""
    state = run_state.read(config.folder)
    pid = state.get("pid")
    running = isinstance(pid, int) and machine.alive(pid)
    if state.get("estado") != "instalando" or running:
        return
    ended = str(state.get("versao"))
    if ended == config.version:
        line = f"previous install: done ({ended})"
        _write(config, line, estado="instalada", instalada=ended, falhas={}, erro=None)
        return
    failures = _failures(state)
    failures[ended] = int(failures.get(ended, 0)) + 1
    reason = f"the installer for {ended} didn't finish (see {state.get('log')})"
    line, kept = f"previous install: failed ({ended})", state.get("instalada")
    _write(config, line, estado="parado", instalada=kept, falhas=failures, erro=reason)


def _failures(state: Mapping[str, object]) -> dict[str, int]:
    """How many setups of each version ended without it."""
    return dict(cast(dict[str, int], state.get("falhas") or {}))


def _clean(config: Config) -> None:
    """Setups of versions that are no longer new, and downloads cut in the middle."""
    current = parse_version(config.version)
    for path in config.folder.glob("Ritmelli-*"):
        with contextlib.suppress(OSError, ValueError):
            cut = path.name.endswith(DOWNLOADING)
            if cut or parse_version(path.name.split("-")[1]) <= current:
                path.unlink()


def _wanted(config: Config) -> Manifest | None:
    """The newer version from the signed manifest. None, with the state written, when
    there is none or its setup failed SETUP_TRIES times."""
    url, https_only = config.manifest_url, config.https_only
    try:
        data = download.fetch(url, MANIFEST_MAX, https_only)
        signature = download.fetch(url + ".sig", SIGNATURE_MAX, https_only)
        found = check(data, signature, config.keys, https_only=https_only)
    except (OSError, ValueError) as error:
        ready = run_state.read(config.folder).get("estado") == "pronta"
        estado = "pronta" if ready else "parado"
        _write(config, f"check: {error}", estado=estado, erro=str(error))
        return None
    version, mine = found.version, config.version
    if parse_version(version) <= parse_version(mine):
        line = f"no new version (installed {mine}, published {version})"
        _write(config, line, estado="parado", nova=None, progresso=0.0)
        return None
    tried = int(_failures(run_state.read(config.folder)).get(version, 0))
    if tried >= SETUP_TRIES:
        line = f"{version}: the installer failed {tried} times; not trying again"
        reason = f"the installer for {version} failed {tried} times; waiting for the next version"
        _write(config, line, estado="parado", progresso=0.0, erro=reason)
        return None
    return found


def _download(config: Config, found: Manifest) -> Path:
    """The setup in the app folder, checked against the manifest. A whole one that is
    already there is not downloaded again."""
    folder, installer = config.folder, found.installer
    # The keys of v0.7.0. The new line has no partial setup.
    new = {
        "versao": found.version,
        "data": found.date,
        "notas": found.notes,
        "notas_en": found.notes_en,
        "tamanho": installer.size,
        "parcial": False,
    }
    run_state.write(folder, {"estado": "baixando", "progresso": 0.0, "nova": new})
    final = folder / f"Ritmelli-{found.version}-setup.exe"
    if final.exists() and download.sha256(final) == installer.sha256:
        return final
    partial = final.with_name(final.name + DOWNLOADING)
    shown = [time.monotonic()]

    def progress(done: float) -> None:
        if time.monotonic() - shown[0] >= 2.0:
            shown[0] = time.monotonic()
            run_state.write(folder, {"estado": "baixando", "progresso": round(done, 3)})

    try:
        with partial.open("wb") as out:
            url, size = installer.url, installer.size
            download.download(url, size, out, config.https_only, progress)
        if download.sha256(partial) != installer.sha256:
            raise Refused("the downloaded installer doesn't match the manifest")
        partial.replace(final)
    finally:
        partial.unlink(missing_ok=True)
    return final


def _install(config: Config, machine: Machine, setup: Path, found: Manifest) -> None:
    """Checks the setup again, here, and starts it silent."""
    version = found.version
    if not setup.exists() or download.sha256(setup) != found.installer.sha256:
        setup.unlink(missing_ok=True)
        line = "the installer changed after it was checked; it will be downloaded again"
        reason = "the downloaded installer changed after it was checked"
        _write(config, line, estado="parado", progresso=0.0, erro=reason)
        return
    log = f"instalador-{version}.log"
    pid = machine.launch([str(setup), *SETUP_ARGS, f"/LOG={config.folder / log}"])
    line, mine = f"installer for {version} started (pid {pid})", config.version
    _write(config, line, estado="instalando", pid=pid, versao=version, de=mine, log=log)


def _write(config: Config, line: str, **changes: object) -> None:
    run_state.write(config.folder, changes)
    _log(line)


def _log(text: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}", flush=True)
