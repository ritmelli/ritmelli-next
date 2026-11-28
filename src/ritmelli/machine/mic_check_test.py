import sys
import threading
import time
from types import ModuleType
from typing import Any

import pytest

from ritmelli.machine import mic_check
from ritmelli.machine.installed import SAVED_KEY, SILENT
from ritmelli.machine.mic_slots_test import Registry

UMC_IN = "IN 1-2 (BEHRINGER UMC 404HD 192k)"
UMC_OUT = "OUT 1-2 (BEHRINGER UMC 404HD 192k)"
MIC = "Microfone (Realtek(R) Audio)"
HEADSET = "Headset (Fone Bluetooth)"
IN_USE = "Linha (Placa Em Uso)"
Device = tuple[str, int, int, str]


class Stream:
    """It gives a frame when it starts, unless its device is silent or wakes only at
    its second open. One whose device refuses does not open."""

    def __init__(self, sd: "Sd", device: int, callback: Any, **_: object) -> None:
        self.name, self.callback = sd.devices[device]["name"], callback
        self.way = sd.ways[self.name]
        self.first = self.name not in [stream.name for stream in sd.opened]
        if self.way == "refuses" or (self.way == "refuses later" and not self.first):
            raise RuntimeError(
                "Error opening stream: Device unavailable [PaErrorCode -9985]"
            )
        sd.opened.append(self)
        self.since, self.open_s = time.monotonic(), 0.0
        self.data = bytearray(b"\x7f" * 8)

    def start(self) -> None:
        if self.way == "gives" or (self.way == "wakes" and not self.first):
            self.callback(self.data, 2)

    def close(self) -> None:
        self.open_s = time.monotonic() - self.since


class Sd(ModuleType):
    """The part of sounddevice the check uses. Each device has a name, WASAPI input
    and output channels, and a way."""

    def __init__(self, *devices: Device) -> None:
        super().__init__("sounddevice")
        self.devices: list[dict[str, Any]] = [
            {"name": name, "hostapi": 1, "default_samplerate": 48000.0}
            | {"max_input_channels": ins, "max_output_channels": outs}
            for name, ins, outs, _ in devices
        ]
        self.ways = {name: way for name, _, _, way in devices}
        self.opened: list[Stream] = []

    def query_hostapis(self) -> list[dict[str, str]]:
        return [{"name": "MME"}, {"name": "Windows WASAPI"}]

    def query_devices(self) -> list[dict[str, Any]]:
        return self.devices

    def WasapiSettings(self, auto_convert: bool) -> bool:
        return auto_convert

    def RawInputStream(self, **settings: Any) -> Stream:
        return Stream(self, **settings)

    RawOutputStream = RawInputStream


@pytest.fixture
def plug(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The devices, in a sounddevice of their own, with short waits."""
    monkeypatch.setattr(mic_check, "WAIT_S", 0.05)
    monkeypatch.setattr(mic_check, "AGAIN_S", 0)
    monkeypatch.setattr(mic_check, "SETTLE_S", 0)

    def devices(*found: Device) -> Sd:
        monkeypatch.setitem(sys.modules, "sounddevice", sd := Sd(*found))
        return sd

    return devices


def test_the_silent_device_goes_in_the_registry(
    plug: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The UMC 404HD after the restart: its input and output open and give nothing.
    The output checked plays silence."""
    reg = Registry()
    monkeypatch.setattr(mic_check, "winreg", reg, raising=False)
    sd = plug((UMC_IN, 2, 0, "silent"), (UMC_OUT, 0, 2, "silent"), (MIC, 2, 2, "gives"))
    summary = f"devices: 3 checked; silent: {UMC_IN}; {UMC_OUT}"
    assert mic_check.after_restart() == mic_check.Report(summary, [UMC_IN, UMC_OUT])
    assert reg.values(SAVED_KEY) == {SILENT: [UMC_IN, UMC_OUT]}
    mic = [bytes(stream.data) for stream in sd.opened if stream.name == MIC]
    assert mic == [b"\x7f" * 8, bytes(8)]


def test_a_silent_device_gets_a_second_chance_with_twice_the_time(plug: Any) -> None:
    sd = plug((HEADSET, 1, 0, "wakes"), (UMC_IN, 2, 0, "silent"))
    checked = {"checked": [HEADSET, UMC_IN], "silent": [UMC_IN], "failed": []}
    assert mic_check.run() == checked
    second = [stream for stream in sd.opened if stream.name == UMC_IN][1]
    assert second.open_s >= 2 * mic_check.WAIT_S


def test_a_device_that_does_not_open_is_not_silent(plug: Any) -> None:
    plug((IN_USE, 2, 0, "refuses"), (MIC, 2, 0, "gives"))
    assert mic_check.run() == {"checked": [MIC], "silent": [], "failed": [IN_USE]}


def test_a_silent_device_that_then_refuses_is_not_checked(plug: Any) -> None:
    plug((UMC_IN, 2, 0, "refuses later"), (MIC, 2, 0, "gives"))
    assert mic_check.run() == {"checked": [MIC], "silent": [], "failed": [UMC_IN]}


def test_the_check_waits_for_the_devices_and_a_driver_error_is_no_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def broken() -> dict[str, list[str]]:
        calls.append("run")
        raise RuntimeError("Error querying device -1")

    monkeypatch.setattr(mic_check, "run", broken)
    monkeypatch.setattr(mic_check.time, "sleep", calls.append)
    summary = "devices: not checked (RuntimeError: Error querying device -1)"
    assert mic_check.after_restart() == mic_check.Report(summary, [])
    assert calls == [mic_check.SETTLE_S, "run"]


def test_a_check_past_the_ceiling_does_not_hold_the_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A driver that hangs on open: past CHECK_MAX_S the check counts as not done, and
    the silent devices of the last check stay."""
    reg = Registry()
    monkeypatch.setattr(mic_check, "winreg", reg, raising=False)
    mic_check.record([UMC_IN])
    held = threading.Event()
    monkeypatch.setattr(mic_check, "run", held.wait)
    monkeypatch.setattr(mic_check, "SETTLE_S", 0)
    monkeypatch.setattr(mic_check, "CHECK_MAX_S", 0.05)
    report = mic_check.after_restart()
    held.set()
    summary = "devices: not checked (still running after 0 s)"
    assert report == mic_check.Report(summary, [], stuck=True)
    assert reg.values(SAVED_KEY) == {SILENT: [UMC_IN]}
