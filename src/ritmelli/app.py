"""The entry point of ritmelli.exe. The first argument picks a mode from MODES.

With no argument the exe exits with 0 at once, with no window and nothing written.
That is what the shortcut and the end of the setup run, and there is no screen yet.
A first argument that is not in MODES exits with 2 at once. The uninstaller waits
for each line an old setup left in its log, so an argument this exe does not know
must never open the app.
"""

import json
import pkgutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import ritmelli
from ritmelli.update import keys, manifest

UNKNOWN = 2


def version() -> str:
    """The version the build gave, from the file the recipe puts next to this script."""
    return Path(__file__).with_name("version.txt").read_text(encoding="ascii")


def describe(args: Sequence[str]) -> int:
    """Writes what this exe is to the file in args: the exe has no console. The
    modules are those of the package inside the exe, found by folder as the kernel
    will find its commands. A build that froze only what app.py imports lists fewer,
    and build_info.py refuses it."""
    if len(args) != 1:
        return UNKNOWN
    found = pkgutil.walk_packages(ritmelli.__path__, "ritmelli.")
    limits = {
        "manifest": manifest.MANIFEST_MAX,
        "signature": manifest.SIGNATURE_MAX,
        "setup": manifest.SETUP_MAX,
    }
    updater = {
        "manifest_url": keys.MANIFEST_URL,
        "keys": keys.KEYS,
        "apps": [manifest.APP],
        "limits": limits,
    }
    described = {
        "version": version(),
        "modes": sorted(MODES),
        "modules": sorted(module.name for module in found),
        "updater": updater,
    }
    Path(args[0]).write_text(json.dumps(described), encoding="utf-8")
    return 0


MODES: dict[str, Callable[[Sequence[str]], int]] = {"--describe": describe}


def main(argv: Sequence[str]) -> int:
    if not argv:
        return 0
    mode = MODES.get(argv[0])
    return UNKNOWN if mode is None else mode(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
