import ntpath
from collections.abc import Mapping
from dataclasses import replace

from ritmelli.machine.protected_folder import Ace, Entry, unprotected_reason

SY = "S-1-5-18"
BA = "S-1-5-32-544"
LS = "S-1-5-19"
US = "S-1-5-32-545"
CO = "S-1-3-0"
TI = "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"
F = 0x1F01FF
M = 0x1301BF
RX = 0x1200A9
GA = 0x10000000
OICI = 3
IO = 8
ROOT = r"C:\Program Files"
APP = r"C:\Program Files\Ritmelli"
EXE = APP + r"\ritmelli.exe"
DLL = APP + r"\_internal\python312.dll"
LOG = APP + r"\microfone\log"
# The ACL of Program Files, which a new folder in it inherits.
FOLDER: tuple[Ace, ...] = (
    (0, 0, F, TI),
    (0, 0, M, SY),
    (0, 0, M, BA),
    (0, 0, RX, US),
    (0, OICI | IO, GA, SY),
    (0, OICI | IO, GA, CO),
    (0, IO, 0xA0000000, US),
)
FILE: tuple[Ace, ...] = ((0, 0, F, SY), (0, 0, F, BA), (0, 0, RX, US))
Disk = Mapping[str, Entry | OSError]


def folder(owner: str = BA, *more: Ace) -> Entry:
    return Entry(True, False, owner, FOLDER + more)


def file(owner: str = BA, *more: Ace) -> Entry:
    return Entry(False, False, owner, FILE + more)


def denied() -> list[str]:
    raise PermissionError(13, "Access is denied")


# The install as the setup leaves it. Above the root only a reparse point counts.
BASE: dict[str, Entry] = {
    "C:\\": Entry(True, False, TI, ((0, 0, F, SY), (0, 0, 0x4, "S-1-5-11"))),
    ROOT: folder(TI),
    APP: folder(),
    EXE: file(),
    APP + r"\_internal": folder(),
    DLL: file(),
    APP + r"\microfone": folder(),
    LOG: folder(BA, (0, OICI, M, LS)),
    LOG + r"\micfx.log": file(LS, (0, 0, M, LS)),
    APP + r"\atualizacao": folder(SY),
}


def check(changes: Disk, path: str = APP, root: str = ROOT) -> str:
    """The reason the rule gives, or "". A key in other case renames the object."""
    tree = {ntpath.normpath(p).lower(): (p, e) for p, e in {**BASE, **changes}.items()}

    def read(path: str) -> Entry | None:
        key = ntpath.normpath(path).lower()
        entry = tree.get(key, ("", None))[1]
        if isinstance(entry, OSError):
            raise entry
        if entry is None or entry.children or not entry.folder or entry.reparse:
            return entry
        inside = [p for k, (p, _) in tree.items() if ntpath.dirname(k) == key]
        return replace(entry, children=lambda: [ntpath.basename(p) for p in inside])

    return unprotected_reason(path, root, read) or ""


def test_the_folder_the_setup_makes_passes() -> None:
    assert check({}) == ""
    upper = {APP + r"\MICROFONE": folder(), APP + r"\MICROFONE\LOG": BASE[LOG]}
    assert check(upper) == ""


def test_what_audiodg_adds_to_the_filter_log_passes() -> None:
    # After a rotation it owns the new log, and CREATOR OWNER gives it full control.
    new, old = file(LS, (0, 0, M, LS), (0, 0, F, LS)), file(BA, (0, 0, M, LS))
    assert check({LOG + r"\micfx.log": new, LOG + r"\micfx.1.log": old}) == ""


def test_an_ace_that_gives_no_write_passes() -> None:
    assert check({EXE: file(BA, (1, 0, M, US))}) == ""
    assert check({EXE: file(BA, (0, IO, M, US))}) == ""


def test_a_folder_not_made_yet_passes_by_its_parents() -> None:
    for path in (APP + r"\New", ROOT + r"\Ritmelli-2", ROOT + r"\.\Ritmelli"):
        assert check({}, path) == ""


def test_the_parents_need_no_listing() -> None:
    parents = {p: replace(BASE[p], children=denied) for p in ("C:\\", ROOT)}
    assert check(parents) == ""


def test_a_long_name_with_a_tilde_passes() -> None:
    for name in ("Ritmelli~Estudio", "Ritmelli~2026", "ABC\U0001f600DE~1"):
        assert check({f"{ROOT}\\{name}": folder()}, f"{ROOT}\\{name}") == ""
