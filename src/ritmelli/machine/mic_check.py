"""The silent device. After the audio restarted, a USB interface (a Behringer UMC
404HD, on the Thesycon TUSBAUDIO driver of many interfaces) opened with no error and
gave no frame, on any input or output, until its cable was pulled. So after each
restart every active device is opened and its frames counted. The silent ones go in
the registry, where the app looks again when it opens, and in the result the setup
shows on its last page.
"""

import contextlib
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

from ritmelli.machine.installed import SAVED_KEY, SILENT

if sys.platform == "win32":  # the tests bring a registry of their own
    import winreg

WAIT_S = 2.0  # what each device has for its first frame
AGAIN_S = 1.0  # before the second chance
SETTLE_S = 2.0  # from the restart to the check: the devices come back one by one
CHECK_MAX_S = 30.0  # the whole check: a driver that hangs does not hold the setup

# A stream to open: the PortAudio index, the device, "in" or "out", the channels.
Target = tuple[int, dict[str, Any], str, int]


@dataclass(frozen=True)
class Report:
    """The check after a restart: the line for the setup log, the silent devices, and
    True when it still runs inside a driver."""

    summary: str
    silent: list[str]
    stuck: bool = False


def device_of(name: str) -> str:
    """What a Windows name is on, the device whose cable is pulled: the last
    parenthesis, with those inside it. "Alto-falantes (Realtek(R) Audio)" gives
    "Realtek(R) Audio". Without a parenthesis at the end, the name."""
    if not name.endswith(")"):
        return name
    depth = 0
    for i in range(len(name) - 1, 0, -1):
        depth += {")": 1, "(": -1}.get(name[i], 0)
        if depth == 0:
            return name[i + 1 : -1]
    return name


def _listen(
    sd: Any, targets: list[Target], wait_s: float
) -> tuple[list[str], list[str]]:
    """Opens the targets together and waits up to wait_s for the first frame of each.
    The names that opened and gave nothing, and those that did not open."""
    frames: dict[tuple[int, str], int] = {}
    opened: list[tuple[tuple[int, str], str, Any]] = []
    failed: list[str] = []
    for index, device, kind, channels in targets:
        key = (index, kind)
        frames[key] = 0

        def count(data: Any, n: int, *_: object, key: tuple[int, str] = key) -> None:
            if key[1] == "out":
                data[:] = bytes(len(data))  # silence: the output checked plays nothing
            frames[key] += n

        # Raw: frames are only counted, and the streams of arrays would need NumPy.
        stream_type = sd.RawInputStream if kind == "in" else sd.RawOutputStream
        try:
            stream = stream_type(
                device=index,
                channels=channels,
                samplerate=device["default_samplerate"],
                dtype="float32",
                extra_settings=sd.WasapiSettings(auto_convert=True),
                callback=count,
            )
            stream.start()
            opened.append((key, device["name"], stream))
        except Exception:  # in exclusive use by another program, say: not silent
            failed.append(device["name"])
    end = time.monotonic() + wait_s
    while time.monotonic() < end and any(frames[key] == 0 for key, _, _ in opened):
        time.sleep(0.02)
    for _, _, stream in opened:
        with contextlib.suppress(Exception):
            stream.close()
    return sorted({name for key, name, _ in opened if frames[key] == 0}), failed


def run() -> dict[str, list[str]]:
    """Each active input and output of Windows, by WASAPI as the app opens them. A
    silent one gets a second chance, with twice the time: a Bluetooth headset takes
    a while to open its voice channel. The devices checked, the silent ones, and
    those that did not open, which are not silent."""
    import sounddevice as sd

    apis = sd.query_hostapis()
    wasapi = next((i for i, api in enumerate(apis) if "WASAPI" in api["name"]), None)
    targets: list[Target] = [
        (index, device, kind, channels)
        for index, device in enumerate(sd.query_devices())
        if device["hostapi"] == wasapi and "[Loopback]" not in device["name"]
        for kind, channels in (
            ("in", device["max_input_channels"]),
            ("out", device["max_output_channels"]),
        )
        if channels > 0
    ]
    silent, failed = _listen(sd, targets, WAIT_S)
    if silent:
        time.sleep(AGAIN_S)
        again = [target for target in targets if target[1]["name"] in silent]
        silent, refused = _listen(sd, again, WAIT_S * 2)
        failed += refused  # silent, then refused: not measured, so not checked
    checked = sorted({target[1]["name"] for target in targets} - set(failed))
    return {"checked": checked, "silent": silent, "failed": sorted(set(failed))}


def record(silent: list[str]) -> None:
    """The silent devices of the last check, in the registry. An empty list deletes
    the value without making the key: the uninstall leaves nothing behind."""
    with contextlib.suppress(FileNotFoundError):
        if silent:
            with winreg.CreateKeyEx(
                winreg.HKEY_LOCAL_MACHINE, SAVED_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, SILENT, 0, winreg.REG_MULTI_SZ, silent)
        else:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, SAVED_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, SILENT)


def after_restart() -> Report:
    """The check, in a thread of its own: one that a driver breaks, or that runs past
    CHECK_MAX_S, counts as not done, and the setup goes on. One that checked nothing,
    as in a session with no audio, leaves the registry as it was."""
    time.sleep(SETTLE_S)
    box: list[dict[str, list[str]] | str] = []

    def check() -> None:
        try:
            box.append(run())
        except Exception as error:  # any error of a driver: no check
            box.append(f"{type(error).__name__}: {error}")

    thread = threading.Thread(target=check, daemon=True)
    thread.start()
    thread.join(CHECK_MAX_S)
    stuck = not box
    found = f"still running after {CHECK_MAX_S:.0f} s" if stuck else box[0]
    if isinstance(found, str):
        return Report(f"devices: not checked ({found})", [], stuck)
    summary = f"devices: {len(found['checked'])} checked"
    if found["silent"]:
        summary += f"; silent: {'; '.join(found['silent'])}"
    if found["failed"]:
        summary += f"; couldn't open: {'; '.join(found['failed'])}"
    if found["checked"]:
        record(found["silent"])
    return Report(summary, found["silent"])
