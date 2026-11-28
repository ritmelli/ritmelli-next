from pathlib import Path

from ritmelli.machine import filter_dll
from ritmelli.machine.filter_dll_test import (
    BUILDER,
    DIGEST,
    KEY,
    PC,
    START,
    STATUS,
    STOP,
    app_dll,
    sha,
)
from ritmelli.machine.filter_dll_test import pc as pc

OTHER = "b" * 64
REPLACED = {
    "new sources, only the DLL changed": (b"0.900.1", OTHER, True, ""),
    "v0.7.0 put back by hand, a microphone changed": (b"0.7.0", DIGEST, False, ""),
    "v0.7.0 put back, the builder past the timeout": (b"0.7.0", DIGEST, False, BUILDER),
}


def test_new_sources_or_v0_7_0_put_back_stop_the_sound_once(
    pc: PC, tmp_path: Path
) -> None:
    late = "the AudioEndpointBuilder didn't restart (-1): it ran past 60.0 s"
    for n, (case, (old, saved, only_service, pc.slow)) in enumerate(REPLACED.items()):
        pc.calls.clear()
        pc.registry.keys[KEY] = {"_sources": saved, "_dll_sha256": sha(b"0.900.1")}
        dll, installed = app_dll(tmp_path / str(n), b"0.900.2", installed=old)
        assert filter_dll.place(dll, str(installed.parent))
        pc.calls.append("mic setup")
        assert filter_dll.restart(only_service) == (late if pc.slow else None)
        replaced = ["icacls.exe", STOP, STATUS, "copy", "regsvr32.exe", "mic setup"]
        builder = [] if only_service else [BUILDER]
        assert pc.calls == [*replaced, *builder, START, STATUS], case
        assert installed.read_bytes() == b"0.900.2"
        assert pc.pair() == {"_sources": DIGEST, "_dll_sha256": sha(b"0.900.2")}
        assert pc.audio == "Running"
