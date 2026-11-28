from dataclasses import replace

from ritmelli.machine.protected_folder import Entry
from ritmelli.machine.protected_folder_test import (
    APP,
    BA,
    DLL,
    EXE,
    IO,
    LOG,
    LS,
    OICI,
    ROOT,
    RX,
    TI,
    US,
    F,
    M,
    check,
    denied,
    file,
    folder,
)

ME = "S-1-5-21-1111111111-2222222222-3333333333-1001"
PARENT = ROOT + r"\Parent"
NEW = ROOT + r"\Parent\Ritmelli"


def test_a_write_right_for_anyone_else_fails() -> None:
    for bit in (1, 2, 4, 6, 8, 16, 18, 19, 28, 30):
        disk = {PARENT: folder(BA, (0, 0, RX | 1 << bit, US)), NEW: folder()}
        assert f"{PARENT} lets {US}" in check(disk, NEW)
    for sid, flags in ((US, OICI), (US, OICI | IO), ("S-1-3-1", OICI | IO)):
        assert f"{APP} lets {sid}" in check({APP: folder(BA, (0, flags, M, sid))})
    assert f"{DLL} lets {US}" in check({DLL: file(BA, (0, 0, 0x2, US))})
    assert f"{ROOT} lets {US}" in check({ROOT: folder(TI, (0, 0, RX | 0x40, US))})
    writable = {PARENT: folder(BA, (0, OICI, M, US))}
    assert f"{PARENT} lets {US}" in check(writable, PARENT + r"\New")


def test_local_service_outside_its_log_rights_fails() -> None:
    internal = {APP + r"\_internal": folder(BA, (0, OICI, M, LS))}
    assert f"_internal lets {LS}" in check(internal)
    assert f"{LOG} lets {LS}" in check({LOG: folder(BA, (0, OICI, M | 1 << 18, LS))})
    assert f"{LOG} is owned by {LS}" in check({LOG: folder(LS, (0, OICI, M, LS))})
    assert f"{LOG} is owned by {LS}" in check({LOG: file(LS, (0, 0, F, LS))})
    assert f"{DLL} is owned by {LS}" in check({DLL: file(LS)})
    full = {LOG + r"\micfx.log": file(BA, (0, 0, F, LS))}
    assert f"micfx.log lets {LS}" in check(full)
    sibling = {LOG + "\u200d": folder(BA, (0, OICI, M, LS))}
    assert f"lets {LS}" in check(sibling)


def test_an_owner_or_a_dacl_outside_the_rule_fails() -> None:
    assert f"{EXE} is owned by {ME}" in check({EXE: file(ME)})
    parent = {PARENT: folder(ME), NEW: folder()}
    assert f"{PARENT} is owned by {ME}" in check(parent, NEW)
    assert f"{EXE} has a null DACL" in check({EXE: Entry(False, False, BA, None)})
    assert "type 5" in check({EXE: Entry(False, False, BA, ((5, 0, 0, None),))})
    unreadable = {DLL: PermissionError(13, "Access is denied")}
    assert f"couldn't read {DLL}" in check(unreadable)
    unlisted = {APP + r"\_internal": replace(folder(), children=denied)}
    assert "couldn't list" in check(unlisted)


def test_a_reparse_point_fails() -> None:
    junction = Entry(True, True, BA, ())
    for path in (APP + r"\_internal", LOG + r"\j", APP):
        assert f"{path} is a reparse point" in check({path: junction})
    for path in (ROOT + r"\J\Ritmelli", ROOT + r"\J\New"):
        assert r"\J is a reparse point" in check({ROOT + r"\J": junction}, path)
    assert f"{EXE} is not a folder" in check({}, EXE)


def test_a_name_windows_cannot_open_or_check_fails() -> None:
    for name in (LOG + r"\x.", APP + r"\_internal\a "):
        assert "can't open" in check({name: file(LS)})
    for parent in ("Foo ", "Foo.", "Foo. ", r"Foo.\.."):
        assert "can't open" in check({}, f"{ROOT}\\{parent}\\Ritmelli")
    assert "can't open" in check({}, APP, ROOT + " ")
    for long in ("x" * 230, "\U0001f3b5" * 115):
        assert "too long" in check({f"{LOG}\\{long}": folder()})
    for long in ("x" * 250, "\U0001f3b5" * 125, "new\\" + "x" * 245):
        assert "too long" in check({}, f"{ROOT}\\{long}")
    for short in (r"C:\PROGRA~1\Ritmelli", r"C:\PROGRA~1.\Ritmelli"):
        assert "short (8.3)" in check({}, short)
    for short in (ROOT + r"\RITMEL~1", ROOT + "\\RITMEL~1 ", APP + r"\RITMEL~1.EXE"):
        assert "short (8.3)" in check({}, short)


def test_a_folder_outside_the_root_fails() -> None:
    for path in (r"C:\Ritmelli", APP + r"\..\..\Ritmelli", ROOT):
        assert "outside" in check({}, path)
    assert r"C:\Other doesn't exist" in check({}, r"C:\Other\Ritmelli", r"C:\Other")
    assert "not an absolute path" in check({}, "Ritmelli")
