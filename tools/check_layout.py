import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
LINE_LIMIT = 300
LIMITED_FOLDERS = ("ritmelli/features", "ritmelli/kernel")
CORE_FOLDER = "ritmelli/audio/core"
CORE_IMPORTS = (
    "numpy",
    "math",
    "time",
    "collections",
    "dataclasses",
    "typing",
    "ritmelli.audio.messages",
    "ritmelli.audio.core",
)


def is_allowed(name: str) -> bool:
    return any(name == root or name.startswith(f"{root}.") for root in CORE_IMPORTS)


def imported_names(path: Path) -> list[str]:
    package = path.relative_to(SRC).parent.parts
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_bytes())):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = (
                ".".join(package[: len(package) + 1 - node.level]) if node.level else ""
            )
            module = ".".join(part for part in (base, node.module) if part)
            names += [
                module if is_allowed(module) else f"{module}.{alias.name}"
                for alias in node.names
            ]
    return names


def problems() -> list[str]:
    found: list[str] = []
    for folder in LIMITED_FOLDERS:
        for path in sorted((SRC / folder).rglob("*.py")):
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count > LINE_LIMIT:
                found.append(
                    f"{path.relative_to(ROOT).as_posix()}: {count} lines, the limit is"
                    f" {LINE_LIMIT}. Split it: one command, reaction or operation per file."
                )
    for path in sorted((SRC / CORE_FOLDER).rglob("*.py")):
        for name in imported_names(path):
            if not is_allowed(name):
                found.append(
                    f"{path.relative_to(ROOT).as_posix()}: imports {name}. audio/core imports"
                    " only numpy, math, time, collections, dataclasses, typing and"
                    " ritmelli.audio.messages. Move the code that needs it out of audio/core."
                )
    return found


if __name__ == "__main__":
    lines = problems()
    for line in lines:
        print(line)
    sys.exit(1 if lines else 0)
