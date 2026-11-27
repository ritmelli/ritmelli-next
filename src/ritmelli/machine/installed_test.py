import re
from pathlib import Path

from ritmelli.machine import installed

MICFX = Path(__file__).parents[3] / "filter" / "apo" / "micfx.cpp"
GUID = re.compile(r"\{0x(\w+), 0x(\w+), 0x(\w+), \{([^}]+)\}\}")


def test_the_filter_has_the_same_clsids_and_saved_key() -> None:
    """The filter keeps its own copy: the CLSIDs it registers, and where it reads the
    vendor MFX that each host runs."""
    source = MICFX.read_text(encoding="utf-8")
    ours = source[source.index("CLSID_MicFx =") : source.index("kCaptura[]")]
    clsids: list[str] = []
    for a, b, c, rest in GUID.findall(ours):
        tail = "".join(f"{int(byte, 16):02X}" for byte in rest.split(","))
        head = f"{int(a, 16):08X}-{int(b, 16):04X}-{int(c, 16):04X}"
        clsids.append(f"{{{head}-{tail[:4]}-{tail[4:]}}}")
    assert clsids == list(installed.OUR_CLSIDS)
    saved = installed.SAVED_KEY.replace("\\", "\\\\")
    assert f'kSalvo[] = L"{saved}";' in source
    assert f'L"{installed.HOSTED}%d"' in source
