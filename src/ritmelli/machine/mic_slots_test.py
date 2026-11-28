from __future__ import annotations

import pytest

from ritmelli.machine import mic_slots
from ritmelli.machine.installed import (
    ANY_NODE,
    APO_KEY,
    ASSOCIATION,
    CAPTURE_KEY,
    COPY_VERSION,
    EFX,
    EFX_LIST,
    EFX_MODES,
    ENHANCEMENTS_OFF,
    FILTER_CLSID,
    HOST_CLSIDS,
    HOSTED,
    LFX,
    MFX_LIST,
    MFX_MODES,
    MISSING,
    MODE_DEFAULT,
    MODE_RAW,
    NO_ENHANCEMENTS,
    OUR_CLSIDS,
    SAVED_KEY,
    SFX,
    SFX_MODES,
)

Data = str | int | list[str]
SZ = 1
DWORD = 4
MULTI = 7
EP = "{4f6ea1d0-a906-4f42-83ac-2ab996490575}"
EP2 = "{0b1c2d3e-4f50-4617-8899-aabbccddeeff}"
LAPTOP_EFX = "{8338CED2-0837-11DC-8314-0800200C9A66}"
ECHO_MFX = "{70306EF0-7851-11DC-8314-0800200C9A66}"
MFX_2 = "{11111111-2222-4333-8444-555555555555}"
SFX_2 = "{22222222-3333-4444-8555-666666666666}"
MODES = [MODE_DEFAULT, MODE_RAW, "{98951333-B9CD-48B1-A0A3-FF40682D73F7}"]


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

    def DeleteKey(self, root: str, sub: str) -> None:
        del self.keys[f"{root}\\{sub}".lower()]

    def EnumValue(self, key: str, index: int) -> tuple[str, Data, int]:
        return _nth(list(self.keys[key].values()), index)

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

    def laptop(self, mfx_modes: list[str], endpoint: str = EP) -> dict[str, Data]:
        """An EFX and two MFX in lists, the last MFX the echo canceller."""
        lists = {EFX_LIST: [LAPTOP_EFX], MFX_LIST: [MFX_2, ECHO_MFX], EFX_MODES: MODES}
        return self.mic(
            {ASSOCIATION: ANY_NODE, **lists, MFX_MODES: mfx_modes}, endpoint
        )


@pytest.fixture
def reg(monkeypatch: pytest.MonkeyPatch) -> Registry:
    """What regsvr32 writes for the filter and the hosts, and the APO registration of
    the echo canceller."""
    fake = Registry()
    monkeypatch.setattr(mic_slots, "winreg", fake, raising=False)
    for clsid in OUR_CLSIDS:
        fake.CreateKeyEx("HKLM", rf"SOFTWARE\Classes\CLSID\{clsid}\InprocServer32")
        ours = fake.CreateKeyEx("HKLM", rf"{APO_KEY}\{clsid}")
        fake.SetValueEx(ours, "FriendlyName", 0, SZ, "Ritmelli Microfone")
        fake.SetValueEx(ours, "Flags", 0, DWORD, 0xE)
    vendor = fake.CreateKeyEx("HKLM", rf"{APO_KEY}\{ECHO_MFX}")
    fake.SetValueEx(vendor, "FriendlyName", 0, SZ, "CFMAPOCAP")
    fake.SetValueEx(vendor, "Flags", 0, DWORD, 0xF)
    return fake


def test_the_vendor_original_is_saved_and_comes_back_value_by_value(
    reg: Registry,
) -> None:
    before = reg.mic({ASSOCIATION: ANY_NODE, SFX: SFX_2, EFX: LAPTOP_EFX})
    assert mic_slots.put_on(EP)
    efx = {EFX_LIST: [LAPTOP_EFX, FILTER_CLSID], EFX_MODES: [MODE_DEFAULT, MODE_RAW]}
    assert reg.fx() == {ASSOCIATION: ANY_NODE, SFX: SFX_2, LFX: FILTER_CLSID, **efx}
    created = [LFX, SFX_MODES, EFX_LIST, EFX_MODES, MFX_LIST]
    saved = {ENHANCEMENTS_OFF: 0, MISSING: created, COPY_VERSION: 3}
    assert reg.values(rf"{SAVED_KEY}\{EP}") == {**before, **saved}
    assert mic_slots.give_back(EP)
    assert (reg.fx(), mic_slots.give_back(EP)) == (before, False)


def test_an_echo_canceller_that_covers_raw_runs_inside_a_host(reg: Registry) -> None:
    before = reg.laptop(MODES)
    assert mic_slots.put_on(EP)
    fx, host = reg.fx(), reg.values(rf"{APO_KEY}\{HOST_CLSIDS[0]}")
    assert (fx[EFX_LIST], fx[MFX_MODES]) == ([LAPTOP_EFX, FILTER_CLSID], MODES)
    assert (fx[MFX_LIST], reg.values(SAVED_KEY)) == (
        [MFX_2, HOST_CLSIDS[0]],
        {f"{HOSTED}0": ECHO_MFX},
    )
    assert host == {"FriendlyName": "Ritmelli Microfone", "Flags": 0xF}
    assert mic_slots.give_back(EP)
    assert reg.fx() == before
    mic_slots.forget_hosts()
    mic_slots.remove_com()
    assert reg.values(SAVED_KEY) == {}
    assert not [path for path in reg.keys if any(c.lower() in path for c in OUR_CLSIDS)]
    assert reg.values(rf"{APO_KEY}\{ECHO_MFX}")["Flags"] == 0xF


def test_a_vendor_mfx_without_raw_keeps_its_list(reg: Registry) -> None:
    before = reg.laptop([MODE_DEFAULT])
    assert mic_slots.put_on(EP)
    assert (reg.fx()[MFX_LIST], reg.values(SAVED_KEY)) == ([MFX_2, ECHO_MFX], {})
    assert mic_slots.give_back(EP)
    assert reg.fx() == before


def test_putting_the_filter_on_twice_changes_nothing(reg: Registry) -> None:
    """The second run of the mic setup leaves the sound alone. Two microphones with
    the same echo canceller share a host."""
    reg.laptop(MODES)
    reg.laptop(MODES, EP2)
    assert mic_slots.put_on(EP) and mic_slots.put_on(EP2)
    assert reg.values(SAVED_KEY) == {f"{HOSTED}0": ECHO_MFX}
    after = {path: dict(values) for path, values in reg.keys.items()}
    assert not (mic_slots.put_on(EP) or mic_slots.put_on(EP2))
    assert reg.keys == after


def test_what_the_filter_created_comes_off_and_enhancements_go_back_off(
    reg: Registry,
) -> None:
    props = rf"{CAPTURE_KEY}\{EP}\Properties"
    assert reg.mic({}, off=1) == {}
    assert mic_slots.put_on(EP)
    assert (reg.fx()[ASSOCIATION], reg.values(props)[NO_ENHANCEMENTS]) == (ANY_NODE, 0)
    created = [ASSOCIATION, LFX, SFX, SFX_MODES, EFX_LIST, EFX_MODES, MFX_LIST]
    saved = {ENHANCEMENTS_OFF: 1, MISSING: created, COPY_VERSION: 3}
    assert reg.values(rf"{SAVED_KEY}\{EP}") == saved
    assert mic_slots.give_back(EP)
    assert (reg.fx(), reg.values(props)[NO_ENHANCEMENTS]) == ({}, 1)


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
    reg.SetValueEx(reg.OpenKey("HKLM", gone), "DeviceState", 0, DWORD, 1)
    with pytest.raises(PermissionError):
        mic_slots.put_on(EP2)
