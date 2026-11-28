"""The protected folder rule.

Both SYSTEM tasks run ritmelli.exe from the app folder, and the update task runs
the downloaded setup from it: that is safe only if no one but the system and the
administrators can change what is in it. The setup checks the same rule, since a
stricter exe would remove the tasks the setup had just made.
"""

import ctypes
import ntpath
import os
import re
import sys
from collections.abc import Callable
from ctypes import byref
from dataclasses import dataclass

SYSTEM = "S-1-5-18"
ADMINISTRATORS = "S-1-5-32-544"
TRUSTED_INSTALLER = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
LOCAL_SERVICE = "S-1-5-19"
CREATOR_OWNER = "S-1-3-0"
OWNERS = frozenset((SYSTEM, ADMINISTRATORS, TRUSTED_INSTALLER))
CHANGE_ACL = 0x40000 | 0x80000 | 0x10000000  # WRITE_DAC, WRITE_OWNER, GENERIC_ALL
# Write data, append or create, write EA, delete child, write attributes (enough
# to turn an empty folder into a junction), delete, GENERIC_WRITE and CHANGE_ACL
WRITE = 0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000000 | CHANGE_ACL
# Inherit-only ACEs count: what is made after the check inherits them.
INHERIT_ONLY = 0x08
ALLOW = (0, 9)  # ACCESS_ALLOWED and its callback
DENY = (1, 6, 10, 12)  # They only take access away.
# Without \\?\ Windows says a longer path does not exist, and it would pass unchecked.
MAX_PATH = 260

Ace = tuple[int, int, int, str | None]
Read = Callable[[str], "Entry | None"]


@dataclass(frozen=True)
class Entry:
    """One object on the disk. Each ACE is its type, flags, mask and SID."""

    folder: bool
    reparse: bool
    owner: str | None
    dacl: tuple[Ace, ...] | None
    children: Callable[[], list[str]] | None = None


def _sid(kernel: ctypes.CDLL, advapi: ctypes.CDLL, pointer: int) -> str | None:
    text = ctypes.c_wchar_p()
    if not advapi.ConvertSidToStringSidW(ctypes.c_void_p(pointer), byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    value = text.value
    kernel.LocalFree(text)
    return value


def _aces(kernel: ctypes.CDLL, advapi: ctypes.CDLL, dacl: int) -> tuple[Ace, ...]:
    aces: list[Ace] = []
    for i in range(ctypes.c_uint16.from_address(dacl + 4).value):
        ace = ctypes.c_void_p()
        if not advapi.GetAce(ctypes.c_void_p(dacl), i, byref(ace)):
            raise ctypes.WinError(ctypes.get_last_error())
        start = ace.value or 0
        kind, flags = ctypes.string_at(start, 2)
        known = kind in (0, 1, 9, 10)  # the mask at +4 and the SID at +8
        mask = ctypes.c_uint32.from_address(start + 4).value if known else 0
        sid = _sid(kernel, advapi, start + 8) if known else None
        aces.append((kind, flags, mask, sid))
    return tuple(aces)


def _read_disk(path: str) -> Entry | None:
    """One object, from a handle that does not follow a reparse point. A folder is
    listed only when the tree asks: a parent may deny it where reading passes."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    # READ_CONTROL | FILE_READ_ATTRIBUTES, OPEN_EXISTING,
    # FILE_FLAG_BACKUP_SEMANTICS (opens a folder) | FILE_FLAG_OPEN_REPARSE_POINT
    opened = kernel.CreateFileW(path, 0x20080, 7, None, 3, 0x02200000, None)
    if opened in (None, ctypes.c_void_p(-1).value):
        error = ctypes.get_last_error()
        if error in (2, 3):
            return None
        raise ctypes.WinError(error)
    handle = ctypes.c_void_p(opened)
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        info = ctypes.create_string_buffer(52)  # BY_HANDLE_FILE_INFORMATION
        if not kernel.GetFileInformationByHandle(handle, info):
            raise ctypes.WinError(ctypes.get_last_error())
        attributes = int.from_bytes(info.raw[:4], "little")
        # SE_FILE_OBJECT; OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
        error = advapi.GetSecurityInfo(
            handle, 1, 0x5, byref(owner), None, byref(dacl), None, byref(descriptor)
        )
        if error:
            raise ctypes.WinError(error)
        sid = _sid(kernel, advapi, owner.value) if owner.value else None
        aces = _aces(kernel, advapi, dacl.value) if dacl.value else None
    finally:
        kernel.LocalFree(descriptor)
        kernel.CloseHandle(handle)
    folder, reparse = bool(attributes & 0x10), bool(attributes & 0x400)
    children = (lambda: os.listdir(path)) if folder and not reparse else None
    return Entry(folder, reparse, sid, aces, children)


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _short_name(name: str) -> bool:
    """An 8.3 alias (PROGRA~1, RITMEL~1.EXE), but not Ritmelli~2026. The setup
    expands an alias, so it would pass where the exe fails."""
    base, dot, ext = name.rstrip(". ").partition(".")
    sizes = 1 <= _utf16(base) <= 8 and (not dot or 1 <= _utf16(ext) <= 3)
    return sizes and "." not in ext and re.search(r"~[0-9]", base) is not None


def _object_reason(path: str, entry: Entry, in_log: bool) -> str | None:
    if entry.reparse:
        return f"{path} is a reparse point"
    log_file = in_log and not entry.folder
    if entry.owner not in OWNERS and not (log_file and entry.owner == LOCAL_SERVICE):
        return f"{path} is owned by {entry.owner}"
    if entry.dacl is None:
        return f"{path} has a null DACL"
    for kind, flags, mask, sid in entry.dacl:
        inherit_only = flags & INHERIT_ONLY
        # On a file, an inherit-only ACE applies to nothing.
        if (inherit_only and not entry.folder) or kind in DENY:
            continue
        if kind not in ALLOW:
            return f"{path} has an ACE of type {kind}"
        if sid in OWNERS or not mask & WRITE or (inherit_only and sid == CREATOR_OWNER):
            continue
        # A log file LocalService owns gets full control from CREATOR OWNER.
        own_log = log_file and entry.owner == LOCAL_SERVICE
        if in_log and sid == LOCAL_SERVICE and (not mask & CHANGE_ACL or own_log):
            continue
        return f"{path} lets {sid} write or change it (access 0x{mask:08x})"
    return None


def _tree_reason(path: str, entry: Entry, read: Read) -> str | None:
    stack: list[tuple[str, Entry, tuple[str, ...]]] = [(path, entry, ())]
    while stack:
        path, entry, rel = stack.pop()
        # audiodg.exe writes the filter log as LocalService; a file named log is not it.
        in_log = tuple(p.lower() for p in rel[:2]) == ("microfone", "log")
        reason = _object_reason(path, entry, in_log and (len(rel) > 2 or entry.folder))
        if reason:
            return reason
        if entry.children is None:
            continue
        try:
            names = entry.children()
        except OSError as e:
            return f"couldn't list {path}: {e}"
        for name in names:
            child = ntpath.join(path, name)
            if name[-1:] in (".", " "):
                return f"{child} has a name Windows can't open"
            if _utf16(child) >= MAX_PATH:
                return f"{child} is too long to check"
            try:
                found = read(child)
            except OSError as e:
                return f"couldn't read {child}: {e}"
            if found is not None:
                stack.append((child, found, (*rel, name)))
    return None


def _path_reason(folder: str, root: str) -> str | None:
    # Before normpath: Windows drops a trailing dot or space and opens another object.
    names = re.split(r"[\\/]", folder)[1:] + re.split(r"[\\/]", root)[1:]
    cut = any(n not in (".", "..") and n[-1:] in (".", " ") for n in names)
    folder, root = ntpath.normpath(folder), ntpath.normpath(root)
    drive, rest = ntpath.splitdrive(folder)
    if any(_short_name(n) for n in rest.split("\\")):
        return f"{folder} has a short (8.3) name"
    if cut:
        return f"{folder} has a name Windows can't open"
    if not drive or not ntpath.isabs(folder) or not ntpath.isabs(root):
        return f"{folder} is not an absolute path"
    inside = ntpath.normcase(root).rstrip("\\") + "\\"
    if not ntpath.normcase(folder).startswith(inside):
        return f"{folder} is outside {root}"
    if _utf16(folder) >= MAX_PATH:
        return f"{folder} is too long to check"
    return None


def unprotected_reason(
    folder: str | None = None, root: str | None = None, read: Read = _read_disk
) -> str | None:
    """Why the folder (by default, this exe's) fails the rule, or None if it passes."""
    folder = ntpath.dirname(sys.executable) if folder is None else folder
    if root is None:
        root = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
        root = root or r"C:\Program Files"
    if reason := _path_reason(folder, root):
        return reason
    folder, root = ntpath.normpath(folder), ntpath.normpath(root)
    drive, rest = ntpath.splitdrive(folder)
    parts = [p for p in rest.split("\\") if p]
    in_root = len([p for p in ntpath.splitdrive(root)[1].split("\\") if p])
    path = drive + "\\"
    for i in range(len(parts) + 1):
        path = ntpath.join(path, parts[i - 1]) if i else path
        try:
            entry = read(path)
        except OSError as e:
            return f"couldn't read {path}: {e}"
        if entry is None:
            return f"{root} doesn't exist" if i <= in_root else None
        if entry.reparse:
            return f"{path} is a reparse point"
        if not entry.folder:
            return f"{path} is not a folder"
        if i == len(parts):
            return _tree_reason(path, entry, read)
        if i >= in_root and (reason := _object_reason(path, entry, False)):
            return reason
    return None
