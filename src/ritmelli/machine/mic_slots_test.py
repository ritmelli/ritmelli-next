from __future__ import annotations

import pytest

from ritmelli.machine import mic_slots
from ritmelli.machine.installed import ANY_NODE, ASSOCIATION, CAPTURE_KEY
from ritmelli.machine.installed import EFX, EFX_LIST, EFX_MODES, FILTER_CLSID, LFX
from ritmelli.machine.installed import MFX_LIST, MODE_DEFAULT
from ritmelli.machine.installed import MODE_RAW, NO_ENHANCEMENTS, SAVED_KEY
from ritmelli.machine.installed import SFX, SFX_MODES

Data = str | int | list[str]
SZ, DWORD, MULTI = 1, 4, 7
EP = "{4f6ea1d0-a906-4f42-83ac-2ab996490575}"
EP2 = "{0b1c2d3e-4f50-4617-8899-aabbccddeeff}"
# The EFX of a laptop microphone, and the SFX of another vendor.
EFX_FM = "{8338CED2-0837-11DC-8314-0800200C9A66}"
SFX_2 = "{22222222-3333-4444-8555-666666666666}"


class Key(str):
    def __enter__(self) -> Key:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _nth[T](items: list[T], index: int) -> T:
    if index >= len(items):
        raise OSError("no more data")
    return items[index]


class Registry:
    """The part of winreg the slots use, in memory, with paths and names in any case.
    A path in locked cannot be created, as Windows refuses the FxProperties of some
    microphones that left the PC."""

    HKEY_LOCAL_MACHINE, REG_SZ, REG_DWORD, REG_MULTI_SZ = "HKLM", SZ, DWORD, MULTI
    KEY_READ, KEY_SET_VALUE, KEY_ALL_ACCESS = 0x20019, 0x2, 0xF003F

    def __init__(self) -> None:
        self.keys: dict[str, dict[str, tuple[str, Data, int]]] = {}
        self.locked: set[str] = set()

    def OpenKey(self, root: str, sub: str, *_: int) -> Key:
        if (path := f"{root}\\{sub}".lower()) not in self.keys:
            raise FileNotFoundError(path)
        return Key(path)

    def CreateKeyEx(self, root: str, sub: str, *_: int) -> Key:
        path = f"{root}\\{sub}".lower()
        if path in self.locked and path not in self.keys:
            raise PermissionError(13, "Access is denied")
        parts = path.split("\\")
        for end in range(2, len(parts) + 1):
            self.keys.setdefault("\\".join(parts[:end]), {})
        return Key(path)

    def QueryValueEx(self, key: str, name: str) -> tuple[Data, int]:
        if (value := self.keys[key].get(name.lower())) is None:
            raise FileNotFoundError(name)
        return (value[1][:] if isinstance(value[1], list) else value[1]), value[2]

    def SetValueEx(self, key: str, name: str, _: int, kind: int, data: Data) -> None:
        if type(data) is not {SZ: str, DWORD: int, MULTI: list}[kind]:
            raise ValueError("Could not convert the data to the specified type.")
        self.keys[key][name.lower()] = (name, data, kind)

    def DeleteValue(self, key: str, name: str) -> None:
        if self.keys[key].pop(name.lower(), None) is None:
            raise FileNotFoundError(name)

    def EnumKey(self, key: str, index: int) -> str:
        inside = {
            p[len(key) + 1 :].split("\\")[0]
            for p in self.keys
            if p.startswith(key + "\\")
        }
        return _nth(sorted(inside), index)

    def values(self, path: str) -> dict[str, Data]:
        return {
            name: data for name, data, _ in self.keys[rf"hklm\{path}".lower()].values()
        }

    def fx(self, endpoint: str = EP) -> dict[str, Data]:
        return self.values(rf"{CAPTURE_KEY}\{endpoint}\FxProperties")

    def mic(
        self, fx: dict[str, Data], endpoint: str = EP, off: int = 0
    ) -> dict[str, Data]:
        """A microphone in the PC with these slots, and its enhancements on or off."""
        base = rf"{CAPTURE_KEY}\{endpoint}"
        self.SetValueEx(self.CreateKeyEx("HKLM", base), "DeviceState", 0, DWORD, 1)
        props = self.CreateKeyEx("HKLM", base + r"\Properties")
        self.SetValueEx(props, NO_ENHANCEMENTS, 0, DWORD, off)
        key = self.CreateKeyEx("HKLM", base + r"\FxProperties")
        for name, data in fx.items():
            self.SetValueEx(key, name, 0, MULTI if isinstance(data, list) else SZ, data)
        return self.fx(endpoint)


@pytest.fixture
def reg(monkeypatch: pytest.MonkeyPatch) -> Registry:
    fake = Registry()
    monkeypatch.setattr(mic_slots, "winreg", fake, raising=False)
    return fake


def test_the_vendor_original_is_saved_value_by_value(reg: Registry) -> None:
    """In the form v0.7.0 reads to give it back."""
    before = reg.mic({ASSOCIATION: ANY_NODE, SFX: SFX_2, EFX: EFX_FM})
    assert mic_slots.put_on(EP)
    efx = {EFX_LIST: [EFX_FM, FILTER_CLSID], EFX_MODES: [MODE_DEFAULT, MODE_RAW]}
    assert reg.fx() == {ASSOCIATION: ANY_NODE, SFX: SFX_2, LFX: FILTER_CLSID, **efx}
    created = [LFX, SFX_MODES, EFX_LIST, EFX_MODES, MFX_LIST]
    saved = {"_sem_melhorias": 0, "_ausentes": created, "_versao": 3}
    assert reg.values(rf"{SAVED_KEY}\{EP}") == {**before, **saved}


def test_what_the_filter_creates_is_listed_and_enhancements_turn_on(
    reg: Registry,
) -> None:
    """What v0.7.0 reads to delete what we created and turn the enhancements off."""
    props = rf"{CAPTURE_KEY}\{EP}\Properties"
    assert reg.mic({}, off=1) == {}
    assert mic_slots.put_on(EP)
    assert (reg.fx()[ASSOCIATION], reg.values(props)[NO_ENHANCEMENTS]) == (ANY_NODE, 0)
    created = [ASSOCIATION, LFX, SFX, SFX_MODES, EFX_LIST, EFX_MODES, MFX_LIST]
    saved = {"_sem_melhorias": 1, "_ausentes": created, "_versao": 3}
    assert reg.values(rf"{SAVED_KEY}\{EP}") == saved


def test_a_microphone_gone_from_the_pc_is_left_out(reg: Registry) -> None:
    """Windows refuses the FxProperties of some microphones that left the PC. One that
    is in the PC and refuses still fails."""
    reg.mic({})
    gone = rf"{CAPTURE_KEY}\{EP2}"
    reg.SetValueEx(reg.CreateKeyEx("HKLM", gone), "DeviceState", 0, DWORD, 0x31000004)
    reg.CreateKeyEx("HKLM", gone + r"\Properties")
    reg.locked.add(rf"hklm\{gone}\FxProperties".lower())
    assert [mic[0] for mic in mic_slots.microphones()] == [EP2, EP]
    assert [mic[0] for mic in mic_slots.microphones(active_only=True)] == [EP]
    with pytest.raises(mic_slots.LeftOut):
        mic_slots.put_on(EP2)
    assert rf"hklm\{SAVED_KEY}\{EP2}".lower() not in reg.keys
    assert mic_slots.put_on(EP)
    reg.SetValueEx(reg.OpenKey("HKLM", gone), "DeviceState", 0, DWORD, 1)
    with pytest.raises(PermissionError):
        mic_slots.put_on(EP2)
