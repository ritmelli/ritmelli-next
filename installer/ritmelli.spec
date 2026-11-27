# The recipe of ritmelli.exe. build.ps1 runs it with the version in RITMELLI_VERSION.
# It makes dist\ritmelli: the exe and _internal\ next to it. A folder, not one file:
# one file unpacks to a temporary folder at every start, and the setup installs a
# folder anyway.
import os

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
                                                 VarStruct, VSVersionInfo)

VERSION = os.environ["RITMELLI_VERSION"]
version_file = os.path.join(workpath, "version.txt")
with open(version_file, "w", encoding="ascii") as f:
    f.write(VERSION)
icon = os.path.join(SPECPATH, "ritmelli.ico")
# the filter and its sources digest, which build.ps1 makes first; the mic setup takes
# them from _internal\microfone
filter_build = os.path.join(SPECPATH, os.pardir, "filter", "apo", "saida")
filter_files = [(os.path.join(filter_build, name), "microfone") for name in ("micfx.dll", "voz.dll", "micfx.sources")]

a = Analysis(
    [os.path.join(SPECPATH, os.pardir, "src", "ritmelli", "app.py")],
    # the setup takes the icon from _internal\icone
    datas=[(version_file, "."), (icon, "icone"), *filter_files],
    # Modules found by folder have no import to follow, so each one is named here,
    # from the package installed in the venv. The tests stay out: they import pytest.
    hiddenimports=collect_submodules("ritmelli", filter=lambda name: not name.endswith(("_test", "_measure"))),
)
# Properties > Details and the name in Task Manager; a setup checks ProductName
numbers = (*map(int, VERSION.split(".")), 0)
version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo([StringTable("041604B0", [
            StringStruct("CompanyName", "Behling Informática Ltda."),
            StringStruct("FileDescription", "Ritmelli"),
            StringStruct("FileVersion", VERSION),
            StringStruct("InternalName", "ritmelli"),
            StringStruct("LegalCopyright", "Software livre sob a GPLv3 / Free software under the GPLv3"),
            StringStruct("OriginalFilename", "ritmelli.exe"),
            StringStruct("ProductName", "Ritmelli"),
            StringStruct("ProductVersion", VERSION),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
    ])

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ritmelli", console=False, version=version, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="ritmelli")
