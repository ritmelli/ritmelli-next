"""build-info.json: what one build of ritmelli.exe is, for the pipeline that publishes
it and for the test manifest of the crossing. The modules, the modes and what the
update trusts come from inside the frozen exe, by its --describe: they are what the
exe will do, not what the source says. An exe that lost a module of the package or a
mode of app.py is refused.

    build_info.py sources <file>
        writes the sources digest to file, for _internal\\microfone\\micfx.sources
    build_info.py <describe.json> <build-info.json> <artifact>...
        writes build-info.json from what the exe described, or exits with 1
"""

import hashlib
import json
import pkgutil
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import ritmelli
from ritmelli.app import MODES

ROOT = Path(__file__).resolve().parent.parent
FORMAT = 1


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def sources_digest() -> str:
    """A sha256 of the git blob lines at the top of filter/apo/, in name order. A blob
    id is of the content as stored: the line endings of the checkout do not change it,
    and neither does the version the build writes into the DLL. The mic setup copies
    the DLL only when the digest changes, so the sound stops only then."""
    lines = git("ls-tree", "HEAD", "--", "filter/apo/").splitlines()
    blobs = [line for line in lines if line.split()[1] == "blob"]
    return hashlib.sha256("".join(f"{line}\n" for line in blobs).encode()).hexdigest()


def source_modules() -> list[str]:
    """The modules of the package, as the recipe freezes them: without the tests."""
    found = pkgutil.walk_packages(ritmelli.__path__, "ritmelli.")
    return sorted(m.name for m in found if not m.name.endswith(("_test", "_measure")))


def sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def build_info(described: dict[str, Any], artifacts: list[Path]) -> dict[str, Any]:
    modules, modes, source = described["modules"], described["modes"], source_modules()
    if modules != source:
        sys.exit(
            f"only in the source: {sorted(set(source) - set(modules))}; "
            f"only in the exe: {sorted(set(modules) - set(source))}"
        )
    if modes != sorted(MODES):
        sys.exit(f"the exe has the modes {modes}, app.py has {sorted(MODES)}")
    version = described["version"]
    return {
        "format": FORMAT,
        "version": version,
        "commit": git("rev-parse", "HEAD").strip(),
        "channel": "test" if re.fullmatch(r"0\.900\.\d+", version) else "production",
        "artifacts": {
            path.name: {"sha256": sha256(path), "size": path.stat().st_size}
            for path in artifacts
        },
        "modules": modules,
        "modes": modes,
        "updater": described["updater"],
        "filter_sources": sources_digest(),
    }


def main(args: list[str]) -> None:
    if len(args) == 2 and args[0] == "sources":
        Path(args[1]).write_text(sources_digest(), encoding="ascii")
    elif len(args) >= 3:
        described = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        info = build_info(described, [Path(arg) for arg in args[2:]])
        Path(args[1]).write_text(json.dumps(info, indent=1), encoding="utf-8")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
