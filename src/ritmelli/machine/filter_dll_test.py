import contextlib
import hashlib
import ntpath
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

from ritmelli.machine import filter_dll

KEY = filter_dll.SAVED_KEY
DIGEST, OTHER = "a" * 64, "b" * 64
STATUS = "(Get-Service audiosrv).Status"
STOP = "Stop-Service audiosrv -Force -ErrorAction Stop"
START = "Start-Service audiosrv -ErrorAction Stop"
BUILDER = "Restart-Service AudioEndpointBuilder -Force -ErrorAction Stop"
Values = dict[str, object]
Handle = contextlib.nullcontext[Values]


class Registry:
    """The part of winreg the filter DLL uses, in memory. A key is its values."""

    HKEY_LOCAL_MACHINE, KEY_SET_VALUE, REG_SZ = "HKLM", 0x2, 1

    def __init__(self) -> None:
        self.keys: dict[str, Values] = {}

    def OpenKey(self, root: str, path: str, *_: int) -> Handle:
        if path not in self.keys:
            raise FileNotFoundError(path)
        return contextlib.nullcontext(self.keys[path])

    def CreateKeyEx(self, root: str, path: str, *_: int) -> Handle:
        return contextlib.nullcontext(self.keys.setdefault(path, {}))

    def QueryValueEx(self, key: Values, name: str) -> tuple[object, int]:
        if name not in key:
            raise FileNotFoundError(name)
        return key[name], self.REG_SZ

    def SetValueEx(self, key: Values, name: str, _: int, kind: int, data: str) -> None:
        key[name] = data

    def DeleteValue(self, key: Values, name: str) -> None:
        if key.pop(name, None) is None:
            raise FileNotFoundError(name)


class PC:
    """Each program run, in order: PowerShell by its command, the others by name. The
    audio service follows what PowerShell does to it. The slow one is killed."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.args: dict[str, list[str]] = {}
        self.audio, self.regsvr32, self.slow = "Running", 0, ""
        self.registry = Registry()

    def run(self, argv: Sequence[str], timeout: float) -> tuple[int, str]:
        name = ntpath.basename(argv[0])
        call = argv[-1] if name == "powershell.exe" else name
        self.calls.append(call)
        self.args[name] = list(argv[1:])
        if call == STATUS:
            return 0, f"{self.audio}\r\n"
        after = {STOP: "Stopped", BUILDER: "Stopped", START: "Running"}
        self.audio = after.get(call, self.audio)
        if call == self.slow:
            raise TimeoutError(f"{argv[0]} ran past {timeout} s")
        return (self.regsvr32 if name == "regsvr32.exe" else 0), ""

    def pair(self) -> Values:
        return self.registry.keys.get(KEY, {})


@pytest.fixture
def pc(monkeypatch: pytest.MonkeyPatch) -> PC:
    machine, copy = PC(), shutil.copy2

    def copy_in_order(source: str, target: str) -> object:
        machine.calls.append("copy")
        return copy(source, target)

    monkeypatch.setattr(filter_dll, "system32", str)
    monkeypatch.setattr(filter_dll, "run", machine.run)
    monkeypatch.setattr(filter_dll, "winreg", machine.registry, raising=False)
    monkeypatch.setattr(shutil, "copy2", copy_in_order)
    return machine


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def app_dll(tmp: Path, new: bytes, installed: bytes | None = None) -> tuple[str, Path]:
    """The DLL that comes with the app, with its digest, and where it goes."""
    app, folder = tmp / "_internal" / "microfone", tmp / "microfone"
    app.mkdir(parents=True)
    (app / "micfx.dll").write_bytes(new)
    (app / "micfx.sources").write_text(DIGEST, encoding="ascii")
    if installed is not None:
        folder.mkdir()
        (folder / "micfx.dll").write_bytes(installed)
    return str(app / "micfx.dll"), folder / "micfx.dll"


def test_the_first_dll_goes_in_with_the_sound_on(pc: PC, tmp_path: Path) -> None:
    dll, installed = app_dll(tmp_path, b"0.900.1")
    assert not filter_dll.place(dll, str(installed.parent))
    assert installed.read_bytes() == b"0.900.1"
    assert pc.pair() == {"_sources": DIGEST, "_dll_sha256": sha(b"0.900.1")}
    assert pc.calls == ["icacls.exe", "copy", "regsvr32.exe"]
    log = str(installed.with_name("log"))
    assert pc.args == {
        "icacls.exe": [log, "/grant", "*S-1-5-19:(OI)(CI)M", "/L"],
        "regsvr32.exe": ["/s", str(installed)],
    }


def test_the_same_sources_keep_the_dll_and_the_sound(pc: PC, tmp_path: Path) -> None:
    dll, installed = app_dll(tmp_path, b"0.900.2", installed=b"0.900.1")
    pair = {"_sources": DIGEST, "_dll_sha256": sha(b"0.900.1")}
    pc.registry.keys[KEY] = dict(pair)
    assert not filter_dll.place(dll, str(installed.parent))
    assert installed.read_bytes() == b"0.900.1"
    assert pc.pair() == pair
    assert pc.calls == ["icacls.exe", "regsvr32.exe"]


def test_the_same_dll_stays_and_gets_its_digest(pc: PC, tmp_path: Path) -> None:
    dll, installed = app_dll(tmp_path, b"0.900.1", installed=b"0.900.1")
    assert not filter_dll.place(dll, str(installed.parent))
    assert pc.pair() == {"_sources": DIGEST, "_dll_sha256": sha(b"0.900.1")}
    assert pc.calls == ["icacls.exe", "regsvr32.exe"]


def test_new_sources_or_v0_7_0_put_back_stop_the_sound_once(
    pc: PC, tmp_path: Path
) -> None:
    # The filter changed, and only the DLL; or v0.7.0, put back by hand, left its DLL
    # under the digest of the new line and a microphone changed too. The last time the
    # AudioEndpointBuilder, which stops the audio service with it, runs past the timeout.
    late = "the AudioEndpointBuilder didn't restart (-1): it ran past 60.0 s"
    for n, (old, saved, only_service, pc.slow) in enumerate(
        ((b"0.900.1", OTHER, True, ""), (b"0.7.0", DIGEST, False, ""))
        + ((b"0.7.0", DIGEST, False, BUILDER),)
    ):
        pc.calls.clear()
        pc.registry.keys[KEY] = {"_sources": saved, "_dll_sha256": sha(b"0.900.1")}
        dll, installed = app_dll(tmp_path / str(n), b"0.900.2", installed=old)
        assert filter_dll.place(dll, str(installed.parent))
        pc.calls.append("mic setup")
        assert filter_dll.restart(only_service) == (late if pc.slow else None)
        replaced = ["icacls.exe", STOP, STATUS, "copy", "regsvr32.exe", "mic setup"]
        builder = [] if only_service else [BUILDER]
        assert pc.calls == [*replaced, *builder, START, STATUS]
        assert installed.read_bytes() == b"0.900.2"
        assert pc.pair() == {"_sources": DIGEST, "_dll_sha256": sha(b"0.900.2")}
        assert pc.audio == "Running"


def test_a_failure_after_the_stop_starts_the_sound_before_it_rises(
    pc: PC, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    restarted = [STATUS, START, STATUS]
    pc.regsvr32 = 3
    dll, installed = app_dll(tmp_path / "0", b"0.900.2", installed=b"0.7.0")
    with pytest.raises(OSError, match=r"regsvr32 failed \(3\)"):
        filter_dll.place(dll, str(installed.parent))
    assert pc.calls == ["icacls.exe", STOP, STATUS, "copy", "regsvr32.exe", *restarted]

    def held(source: str, target: str) -> None:
        pc.calls.append("copy")
        raise PermissionError(13, "The file is in use by another process")

    pc.calls.clear()
    monkeypatch.setattr(shutil, "copy2", held)
    dll, installed = app_dll(tmp_path / "1", b"0.900.2", installed=b"0.7.0")
    with pytest.raises(PermissionError, match="in use"):
        filter_dll.place(dll, str(installed.parent))
    assert pc.calls == ["icacls.exe", STOP, STATUS, "copy", *restarted]
    assert installed.read_bytes() == b"0.7.0"
    assert pc.audio == "Running"


def test_the_remove_forgets_the_digest_and_keeps_the_hosts(pc: PC) -> None:
    filter_dll.forget()
    host = "{22222222-3333-4444-8555-666666666666}"
    pair = {"_sources": DIGEST, "_dll_sha256": sha(b"0.900.1")}
    pc.registry.keys[KEY] = {**pair, "_hospede0": host}
    filter_dll.forget()
    assert pc.pair() == {"_hospede0": host}
