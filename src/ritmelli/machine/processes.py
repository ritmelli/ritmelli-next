"""The processes of this PC, from a snapshot that opens none, so the update task, as
SYSTEM, sees those of every session. This module is the Windows side of the round."""

import ctypes
import os
import sys
from pathlib import Path

from ritmelli.ports.process.run import spawn_detached

SNAPSHOT_PROCESSES = 0x2  # TH32CS_SNAPPROCESS
QUERY_LIMITED = 0x1000  # PROCESS_QUERY_LIMITED_INFORMATION


class _Entry(ctypes.Structure):
    """PROCESSENTRY32W."""

    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_wchar * 260),
    ]
    th32ProcessID: int
    szExeFile: str


def _processes() -> list[tuple[int, str]]:
    """Each process, by pid and exe name."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snapshot = kernel.CreateToolhelp32Snapshot(SNAPSHOT_PROCESSES, 0)
    if snapshot in (None, ctypes.c_void_p(-1).value):
        return []
    handle = ctypes.c_void_p(snapshot)
    entry = _Entry(dwSize=ctypes.sizeof(_Entry))
    found: list[tuple[int, str]] = []
    try:
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            found.append((entry.th32ProcessID, entry.szExeFile))
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return found


def _image(pid: int) -> str | None:
    """The full path of the exe of the process, or None when it cannot be read."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    opened = kernel.OpenProcess(QUERY_LIMITED, False, pid)
    if not opened:
        return None
    handle = ctypes.c_void_p(opened)
    try:
        path, size = ctypes.create_unicode_buffer(1024), ctypes.c_uint32(1024)
        done = kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
        return path.value if done else None
    finally:
        kernel.CloseHandle(handle)


def app_open() -> bool:
    """A ritmelli.exe of this exe's folder runs, other than this process, such as
    Ritmelli or the mic task. One whose path cannot be read counts as open: in doubt,
    the new version waits."""
    here = Path(sys.executable).parent.resolve()
    mine = os.getpid()
    for pid, name in _processes():
        if pid == mine or name.lower() != "ritmelli.exe":
            continue
        image = _image(pid)
        if image is None or Path(image).parent.resolve() == here:
            return True
    return False


def alive(pid: int) -> bool:
    return any(found == pid for found, _ in _processes())


# The setup, detached: it replaces the ritmelli.exe of the round, which exits right after.
launch = spawn_detached
