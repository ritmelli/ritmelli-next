"""The filter DLL in {app}\\microfone, where audiodg.exe loads it from.

The build writes the version into the DLL, so each version has other bytes. To
replace the DLL the audio service must stop, and every sound of the PC stops with it.
So the DLL is replaced only when the sources digest that comes with it changes. The
digest is saved with the sha256 of the DLL it describes: a PC taken back to v0.7.0
by hand keeps the digest of the new line, next to the DLL of v0.7.0.
"""

import contextlib
import hashlib
import os
import shutil
import sys
from pathlib import Path

from ritmelli.machine.installed import SAVED_KEY, system32
from ritmelli.ports.process.run import run

if sys.platform == "win32":  # the tests bring a registry of their own
    import winreg

TIMEOUT_S = 60.0
POWERSHELL = r"WindowsPowerShell\v1.0\powershell.exe"
# At the root of the key: the sources digest of the DLL in {app}\microfone, and the
# sha256 of that DLL.
SOURCES = "_sources"
DLL_SHA256 = "_dll_sha256"


def _sha256(path: str) -> str:
    with open(path, "rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _powershell(command: str) -> tuple[int, str]:
    return run([system32(POWERSHELL), "-NoProfile", "-Command", command], TIMEOUT_S)


def _state() -> str:
    return _powershell("(Get-Service audiosrv).Status")[1].strip()


def _service(action: str) -> None:
    """Stop or Start of the audio service. Start gets no -Force: with it the command
    fails silently and the PC is left without sound."""
    force = " -Force" if action == "Stop" else ""
    code, out = _powershell(f"{action}-Service audiosrv{force} -ErrorAction Stop")
    if code:
        raise OSError(f"{action}-Service audiosrv failed ({code}): {out.strip()}")
    want = "Stopped" if action == "Stop" else "Running"
    if (state := _state()) != want:
        raise OSError(f"the audio service was '{state}' after the {action}, not {want}")


def _register(dll: str) -> None:
    code, _ = run([system32("regsvr32.exe"), "/s", dll], TIMEOUT_S)
    if code:
        raise OSError(f"regsvr32 failed ({code})")


def _saved(key: str) -> list[object]:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            return [winreg.QueryValueEx(k, name)[0] for name in (SOURCES, DLL_SHA256)]
    except OSError:
        return []


def _save(key: str, sources: str, sha256: str) -> None:
    with winreg.CreateKeyEx(
        winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE
    ) as k:
        winreg.SetValueEx(k, SOURCES, 0, winreg.REG_SZ, sources)
        winreg.SetValueEx(k, DLL_SHA256, 0, winreg.REG_SZ, sha256)


def place(dll: str, folder: str, key: str = SAVED_KEY) -> bool:
    """Puts dll, the filter that comes with the app, in folder and registers it there.
    The caller checks the protected folder first: audiodg.exe would load a DLL another
    program can change. In the log folder LocalService, which runs audiodg.exe, may
    change files but not their rights; /L grants it on the folder itself, never where
    it points.

    True when the audio service stopped to let go of the old DLL: the caller starts it
    again with restart, once, after the microphones. A failure from the stop on starts
    it before the error rises.
    """
    log = os.path.join(folder, "log")
    os.makedirs(log, exist_ok=True)
    grant = [system32("icacls.exe"), log, "/grant", "*S-1-5-19:(OI)(CI)M", "/L"]
    code, out = run(grant, TIMEOUT_S)
    if code:
        raise OSError(f"icacls on the log folder failed ({code}): {out.strip()}")
    target = os.path.join(folder, "micfx.dll")
    sources = Path(dll).with_name("micfx.sources").read_text(encoding="ascii").strip()
    new = _sha256(dll)
    installed = _sha256(target) if os.path.exists(target) else None
    if installed is not None and _saved(key) == [sources, installed]:
        _register(target)
        return False
    if installed in (None, new):
        if installed is None:  # nothing holds it: the sound goes on
            shutil.copy2(dll, target)
        _save(key, sources, new)
        _register(target)
        return False
    try:
        _service("Stop")
        shutil.copy2(dll, target)
        _save(key, sources, new)
        _register(target)
    except BaseException:
        with contextlib.suppress(OSError):
            if _state() != "Running":
                _service("Start")
        raise
    return True


def restart(only_service: bool) -> str | None:
    """After the mic setup changed a microphone or the DLL. The AudioEndpointBuilder
    reads the effects again only when it restarts, and the audio service goes down
    with it. With only_service, when only the DLL changed, the new audiodg.exe loads it
    and the AudioEndpointBuilder, which builds every device again, stays as it is.

    The error of the AudioEndpointBuilder, past the timeout too, or None. An audio
    service that does not come back raises.
    """
    error = None
    if not only_service:
        command = "Restart-Service AudioEndpointBuilder -Force -ErrorAction Stop"
        code, out = -1, f"it ran past {TIMEOUT_S} s"
        with contextlib.suppress(TimeoutError):
            code, out = _powershell(command)
        if code:
            error = f"the AudioEndpointBuilder didn't restart ({code}): {out.strip()}"
    _service("Start")
    return error


def forget(key: str = SAVED_KEY) -> None:
    """The remove, when no microphone keeps the filter: the DLL goes, and so does what
    describes it."""
    with (
        contextlib.suppress(OSError),
        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE) as k,
    ):
        for name in (SOURCES, DLL_SHA256):
            winreg.DeleteValue(k, name)
