"""TERCEIROS.txt, the third-party notices the setup puts in the app folder: each part
that ships with Ritmelli, with the text of its license. build.ps1 runs it after it
freezes the exe, with the python of the build venv:

    third_party.py <dist\\ritmelli> <TERCEIROS.txt>

- the Python packages PyInstaller took: the top names in the PYZ of the exe and in
  _internal\\, each tied to the package of the venv that installed files under it. The
  text is the license files in the .dist-info of that package;
- Python, by the LICENSE.txt of its install, and PyInstaller, whose bootloader is the
  start of ritmelli.exe.

A name of no package in the venv, a package without a license file, or a library of
Python in _internal\\ whose text that LICENSE.txt lacks, stops the build rather than
ship a setup that lacks a notice. The repo keeps no third-party license text: for a
package that ships without its own, take a version that ships it, or add the text to
the repo with the code that reads it.
"""

import re
import sys
from importlib.metadata import Distribution, distribution, packages_distributions
from pathlib import Path

OURS = {"ritmelli", "icone", "microfone"}
LICENSE_NAME = re.compile(r"LICEN[CS]E|COPYING|NOTICE|COPYRIGHT", re.IGNORECASE)
PYTHON_LIBRARIES = {
    "libcrypto-*.dll": "Apache License",
    "libssl-*.dll": "Apache License",
    "libffi-*.dll": "libffi - Copyright",
}
SEE = "consulte o texto / see the text"
BOOTLOADER = (
    "O bootloader do PyInstaller forma o início do ritmelli.exe; a exceção prevista na "
    "licença dele permite distribuir o programa gerado sob outra licença.\n\n"
    "The PyInstaller bootloader forms the beginning of ritmelli.exe; the exception in "
    "its license allows the generated program to be distributed under another license."
)
HEADER = (
    "Ritmelli {version}: avisos de terceiros / third-party notices\n\n"
    "O Ritmelli é software livre, distribuído sob a GPLv3 (LICENSE.txt, nesta pasta). "
    "Ele inclui programas e bibliotecas\nde outros projetos, cada um sob a sua própria "
    "licença. Este arquivo traz a lista desses componentes e, em seguida, o texto\nde "
    "cada licença.\n\n"
    "Ritmelli is free software, distributed under the GPLv3 (LICENSE.txt, in this "
    "folder). It includes software\nand libraries from other projects, each under its "
    "own license. This file lists those components, followed by\nthe text of each "
    "license.\n\n"
)

Section = tuple[str, str, str]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def frozen_names(app: Path) -> set[str]:
    """The top names of what PyInstaller took: the modules in the PYZ of the exe, and
    the folders and .pyd files in _internal\\."""
    from PyInstaller.archive.readers import CArchiveReader

    pyz = CArchiveReader(str(app / "ritmelli.exe")).open_embedded_archive("PYZ.pyz")
    names = {name.split(".")[0] for name in pyz.toc}
    for path in (app / "_internal").iterdir():
        if path.is_dir() and not path.name.endswith(".dist-info"):
            names.add(path.name)
        elif path.suffix == ".pyd":
            names.add(path.name.split(".")[0])
    return names


def python_section(app: Path) -> Section:
    """Python, by the LICENSE.txt of its install, with the text of each library of it
    that the exe carries."""
    python = Path(sys.base_prefix) / "LICENSE.txt"
    text = read(python)
    lacking = sorted(
        path.name
        for pattern, line in PYTHON_LIBRARIES.items()
        for path in (app / "_internal").glob(pattern)
        if line not in text
    )
    if lacking:
        sys.exit(
            f"{python} lacks the text of {lacking}, which the exe carries: build "
            "with the Python of python.org (UV_PYTHON=<its python.exe>)"
        )
    components = (
        "PSF-2.0 e as licenças dos seus componentes / "
        "PSF-2.0 and the licenses of its components"
    )
    return (f"Python {sys.version.split()[0]}", components, text)


def terms(package: Distribution) -> str:
    """The short name of the license, when the metadata gives one in a line."""
    metadata = package.metadata
    named = metadata.get("License-Expression") or metadata.get("License", "")
    return named if named and "\n" not in named and len(named) <= 80 else SEE


def texts(package: Distribution) -> list[tuple[str, str]]:
    """The license files in the .dist-info of the package, and in its licenses\\."""
    return [
        (file.as_posix(), read(Path(package.locate_file(file))))
        for file in package.files or []
        if file.parts[0].endswith(".dist-info")
        and (LICENSE_NAME.search(file.name) or "licenses" in file.parts[1:-1])
    ]


def package_sections(names: set[str]) -> list[Section]:
    """A section for each package of the venv that a frozen name came from, and for
    PyInstaller, whose bootloader is in every exe."""
    found = packages_distributions()
    theirs = {
        name
        for name in names - OURS
        if name not in sys.stdlib_module_names
        and not name.startswith(("pyimod", "pyi_", "_pyi"))
    }
    if stray := sorted(theirs - found.keys()):
        sys.exit(f"names of no package in the venv, so of no license: {stray}")
    sections: list[Section] = []
    missing: list[str] = []
    shipped = {"pyinstaller"}.union(*(found[name] for name in theirs))
    for name in sorted(shipped, key=str.lower):
        package = distribution(name)
        body = "\n\n".join(f"--- {where}\n\n{text}" for where, text in texts(package))
        if not body:
            missing.append(name)
        elif name == "pyinstaller":
            sections.append(
                (
                    f"{name} {package.version}",
                    "GPL-2.0-or-later WITH Bootloader-exception",
                    f"{BOOTLOADER}\n\n{body}",
                )
            )
        else:
            sections.append((f"{name} {package.version}", terms(package), body))
    if missing:
        sys.exit(f"packages without a license file in the venv: {missing}")
    return sections


def write(out: Path, version: str, sections: list[Section]) -> list[str]:
    """Writes the list of the parts, then the text of each, and returns the list."""
    listing = [f"  {title:<40} {terms}" for title, terms, _ in sections]
    rule = "=" * 100
    parts = [
        f"{rule}\n{title} ({terms})\n{rule}\n\n{text}\n"
        for title, terms, text in sections
    ]
    head = HEADER.format(version=version)
    out.write_text(
        head + "\n".join(listing) + "\n\n\n" + "\n\n".join(parts), encoding="utf-8-sig"
    )
    return listing


def main(args: list[str]) -> None:
    if len(args) != 2:
        sys.exit(__doc__)
    app, out = Path(args[0]), Path(args[1])
    sections = [python_section(app), *package_sections(frozen_names(app))]
    version = (app / "_internal" / "version.txt").read_text(encoding="ascii")
    listing = write(out, version, sections)
    print("\n".join(listing))
    print(f"{out}: {len(listing)} parts, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
