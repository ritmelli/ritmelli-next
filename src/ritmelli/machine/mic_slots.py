"""The slots of each microphone: the filter goes on, and the original is saved.

The filter takes two slots, and Windows uses one. The EFX list runs for every stream,
raw included; a driver with no processing modes reads only the LFX.
"""

from __future__ import annotations

import contextlib
import itertools
import sys
from collections.abc import Callable, Iterator
from typing import Any

from ritmelli.machine.installed import ANY_NODE, ASSOCIATION, CAPTURE_KEY
from ritmelli.machine.installed import CREATED_SLOTS, EFX, EFX_LIST, EFX_MODES, LFX
from ritmelli.machine.installed import FILTER_CLSID, OUR_CLSIDS
from ritmelli.machine.installed import MFX_LIST, MODE_DEFAULT, MODE_RAW
from ritmelli.machine.installed import NO_ENHANCEMENTS, SAVED_KEY, SAVED_SLOTS, SFX
from ritmelli.machine.installed import SAVED_VERSION

if sys.platform == "win32":  # the tests bring a registry of their own
    import winreg

NAME = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
DEVICE = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
NOT_PRESENT = 4


class LeftOut(OSError):
    """A microphone the mic setup leaves out with no error: it has no Properties, or
    it left the PC and Windows does not let us create its FxProperties."""


def _open(path: str, access: int) -> winreg.HKEYType:
    return winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, access)


def _create(path: str, access: int) -> winreg.HKEYType:
    return winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, access)


def _read(key: winreg.HKEYType, name: str) -> tuple[Any, int] | None:
    try:
        return winreg.QueryValueEx(key, name)
    except OSError:
        return None


def _get(key: winreg.HKEYType, name: str, default: Any) -> Any:
    return default if (value := _read(key, name)) is None else value[0]


def _upper(key: winreg.HKEYType, name: str) -> list[str]:
    return [str(clsid).upper() for clsid in _get(key, name, [])]


def _each[T](enum: Callable[[Any, int], T], key: winreg.HKEYType) -> Iterator[T]:
    for index in itertools.count():
        try:
            item = enum(key, index)
        except OSError:
            return
        yield item


def ours(fx: winreg.HKEYType) -> bool:
    """The filter or a host is on some slot of these FxProperties."""
    singles = [str(_get(fx, name, "")).upper() for name in (LFX, SFX, EFX)]
    lists = _upper(fx, EFX_LIST) + _upper(fx, MFX_LIST)
    return FILTER_CLSID in singles or any(clsid in OUR_CLSIDS for clsid in lists)


def microphones(active_only: bool = False) -> list[tuple[str, str, str]]:
    """The id, name and device of each microphone. Without active_only, also the
    disabled and unplugged ones: the filter is on them when they come back."""
    found: list[tuple[str, str, str]] = []
    with contextlib.suppress(OSError), _open(CAPTURE_KEY, winreg.KEY_READ) as root:
        for endpoint in _each(winreg.EnumKey, root):
            try:
                with winreg.OpenKey(root, endpoint) as key:
                    if active_only and _get(key, "DeviceState", 0) != 1:
                        continue
                with winreg.OpenKey(root, endpoint + r"\Properties") as props:
                    name, device = _get(props, NAME, "?"), _get(props, DEVICE, "?")
                found.append((endpoint, str(name), str(device)))
            except OSError:
                continue
    return found


def _gone(base: str) -> bool:
    """The microphone left the PC, and has no FxProperties."""
    try:
        with _open(base, winreg.KEY_READ) as key:
            state, kind = winreg.QueryValueEx(key, "DeviceState")
    except OSError:
        return False
    if kind != winreg.REG_DWORD or state & 0xF != NOT_PRESENT:
        return False
    try:
        with _open(base + r"\FxProperties", winreg.KEY_READ):
            return False
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _open_fx(base: str) -> winreg.HKEYType:
    try:
        return _create(base + r"\FxProperties", winreg.KEY_READ | winreg.KEY_SET_VALUE)
    except PermissionError as error:
        if not _gone(base):
            raise
        raise LeftOut(*error.args) from error


def _save(fx: winreg.HKEYType, saved: winreg.HKEYType, off: int) -> None:
    for name in SAVED_SLOTS:
        if (value := _read(fx, name)) is None:
            with contextlib.suppress(OSError):
                winreg.DeleteValue(saved, name)
        else:
            winreg.SetValueEx(saved, name, 0, value[1], value[0])
    winreg.SetValueEx(saved, "_sem_melhorias", 0, winreg.REG_DWORD, 1 if off else 0)
    missing = [name for name in CREATED_SLOTS if _read(fx, name) is None]
    winreg.SetValueEx(saved, "_ausentes", 0, winreg.REG_MULTI_SZ, missing)


def _put_efx(fx: winreg.HKEYType) -> bool:
    """Ours on the LFX and last on the EFX list, the vendor single EFX first on it,
    with the DEFAULT and RAW modes. True when something changed."""
    changed = str(_get(fx, LFX, "")).upper() != FILTER_CLSID
    if changed:
        winreg.SetValueEx(fx, LFX, 0, winreg.REG_SZ, FILTER_CLSID)
    efx = [str(c) for c in _get(fx, EFX_LIST, []) if str(c).upper() != FILTER_CLSID]
    single = str(_get(fx, EFX, ""))
    if single and single.upper() not in [FILTER_CLSID, *(c.upper() for c in efx)]:
        efx.insert(0, single)
    if single:
        winreg.DeleteValue(fx, EFX)
    if _upper(fx, EFX_LIST) != [c.upper() for c in [*efx, FILTER_CLSID]]:
        winreg.SetValueEx(fx, EFX_LIST, 0, winreg.REG_MULTI_SZ, [*efx, FILTER_CLSID])
        changed = True
    modes, have = [str(m) for m in _get(fx, EFX_MODES, [])], _upper(fx, EFX_MODES)
    if missing := [m for m in (MODE_DEFAULT, MODE_RAW) if m not in have]:
        winreg.SetValueEx(fx, EFX_MODES, 0, winreg.REG_MULTI_SZ, modes + missing)
        changed = True
    return changed


def put_on(endpoint: str) -> bool:
    """Puts the filter on the microphone, and saves its original when ours is not on
    it yet: saved again, ours would become the original. Turns the audio enhancements
    on, since without them no effect loads. True when something changed."""
    base = rf"{CAPTURE_KEY}\{endpoint}"
    try:
        props = _open(base + r"\Properties", winreg.KEY_READ)
    except FileNotFoundError as error:
        raise LeftOut(*error.args) from error
    with props:
        off = _get(props, NO_ENHANCEMENTS, 0)
    access = winreg.KEY_ALL_ACCESS
    with _open_fx(base) as fx, _create(rf"{SAVED_KEY}\{endpoint}", access) as saved:
        if changed := not ours(fx):
            _save(fx, saved, off)
        winreg.SetValueEx(saved, "_versao", 0, winreg.REG_DWORD, SAVED_VERSION)
        changed |= _put_efx(fx)
        if _read(fx, ASSOCIATION) is None:
            winreg.SetValueEx(fx, ASSOCIATION, 0, winreg.REG_SZ, ANY_NODE)
            changed = True
    if off:
        with _open(base + r"\Properties", winreg.KEY_SET_VALUE) as props:
            winreg.SetValueEx(props, NO_ENHANCEMENTS, 0, winreg.REG_DWORD, 0)
    return changed or bool(off)
