from codecs import BOM_UTF8
from pathlib import Path

import pytest

import third_party

# what PyInstaller adds, the standard library and our folders: none needs a package
FROZEN = {"pyimod01_archive", "_pyi_rth_utils", "json", "_ssl", "ritmelli", "icone"}


def venv(
    site: Path, licensed: dict[str, str | None], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A site-packages on the path with one package for each name, with its license
    file at that path inside the .dist-info, or with none."""
    for name, where in licensed.items():
        info = site / f"{name}-1.0.dist-info"
        (site / name).mkdir(parents=True)
        info.mkdir()
        (site / name / "__init__.py").write_text("")
        metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\nLicense: MIT\n"
        (info / "METADATA").write_text(metadata)
        files = [f"{name}/__init__.py", f"{info.name}/METADATA"]
        if where:
            (info / where).parent.mkdir(exist_ok=True)
            (info / where).write_text(f"the license of {name}\n")
            files.append(f"{info.name}/{where}")
        (info / "RECORD").write_text("".join(f"{f},,\n" for f in files))
    monkeypatch.syspath_prepend(site)


def test_with_a_license_file_for_each_package_the_notices_hold_every_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    venv(
        tmp_path / "site",
        {
            "pyinstaller": "licenses/COPYING.txt",
            "noted": "LICENSE",
            "not_shipped": None,
        },
        monkeypatch,
    )
    sections = third_party.package_sections(FROZEN | {"noted"})
    out = tmp_path / "TERCEIROS.txt"
    listing = third_party.write(
        out, "0.900.1", [("Python", "PSF-2.0", "psf"), *sections]
    )
    terms = "GPL-2.0-or-later WITH Bootloader-exception"
    assert listing == [
        f"  {'Python':<40} PSF-2.0",
        f"  {'noted 1.0':<40} MIT",
        f"  {'pyinstaller 1.0':<40} {terms}",
    ]
    assert out.read_bytes().startswith(BOM_UTF8 + b"Ritmelli 0.900.1: avisos")
    written = out.read_text(encoding="utf-8-sig")
    assert "--- noted-1.0.dist-info/LICENSE\n\nthe license of noted" in written
    assert third_party.BOOTLOADER in written
    assert "the license of pyinstaller" in written


def test_a_package_without_a_license_file_stops_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    venv(tmp_path, {"pyinstaller": "COPYING.txt", "bare": None}, monkeypatch)
    with pytest.raises(
        SystemExit, match=r"without a license file in the venv: \['bare'\]"
    ):
        third_party.package_sections(FROZEN | {"bare"})


def test_a_library_of_python_whose_text_the_license_lacks_stops_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, python = tmp_path / "ritmelli", tmp_path / "python"
    (app / "_internal").mkdir(parents=True)
    (app / "_internal" / "libssl-3-x64.dll").write_bytes(b"")
    python.mkdir()
    monkeypatch.setattr(third_party.sys, "base_prefix", str(python))
    (python / "LICENSE.txt").write_text("the license of Python\n")
    with pytest.raises(SystemExit, match=r"lacks the text of \['libssl-3-x64.dll'\]"):
        third_party.python_section(app)
    (python / "LICENSE.txt").write_text("the license of Python\n\n  Apache License\n")
    assert "Apache License" in third_party.python_section(app)[2]


def test_a_name_of_no_package_stops_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    venv(tmp_path, {"pyinstaller": "COPYING.txt"}, monkeypatch)
    with pytest.raises(SystemExit, match=r"no package in the venv.*\['stray'\]"):
        third_party.package_sections(FROZEN | {"stray"})
