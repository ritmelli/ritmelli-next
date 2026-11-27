import ast
import sys
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = (
    "__future__ numpy math time collections dataclasses typing"
    " ritmelli.audio.messages ritmelli.audio.core"
).split()
CORE_FIX = (
    "audio/core imports only numpy, math, time, collections, dataclasses, typing"
    " and ritmelli.audio.messages. Move the code that needs it out of audio/core."
)


def allowed(name: str) -> bool:
    return any(name == root or name.startswith(f"{root}.") for root in CORE)


def imported(path: Path) -> list[str]:
    package = ".".join(path.relative_to(ROOT / "src").parent.parts)
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_bytes())):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = resolve_name("." * node.level + (node.module or ""), package)
            names += [
                module if allowed(module) else f"{module}.{a.name}" for a in node.names
            ]
    return names


found: list[str] = []
for path in sorted((ROOT / "src").rglob("*.py")):
    where = path.relative_to(ROOT).as_posix()
    lines = len(path.read_text(encoding="utf-8").splitlines())
    limited = where.startswith(("src/ritmelli/features/", "src/ritmelli/kernel/"))
    if limited and lines > 300:
        found.append(
            f"{where}: {lines} lines, over 300. Split it: one command or operation per file."
        )
    if path.name.startswith("test_"):
        found.append(f"{where}: pytest skips it. Name it {path.name[5:-3]}_test.py.")
    if where.startswith("src/ritmelli/audio/core/"):
        for name in imported(path):
            if not allowed(name):
                found.append(f"{where}: imports {name}. {CORE_FIX}")
for line in found:
    print(line)
sys.exit(1 if found else 0)
