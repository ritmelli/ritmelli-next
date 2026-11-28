"""A text of installed.py written in quotes in another file. If one side changes and
the other does not, the new line stops finding what v0.7.0 left on the PC. A test
keeps the v0.7.0 value on its own, so the tests are left out."""

import ast
from pathlib import Path

INSTALLED = "src/ritmelli/machine/installed.py"


def text(node: ast.expr, known: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Name):
        return known.get(node.value.id)
    if isinstance(node, ast.JoinedStr):
        parts = [text(part, known) for part in node.values]
        return None if None in parts else "".join(parts)
    return None


def pairs(target: ast.expr, value: ast.expr, known: dict[str, str]) -> dict[str, str]:
    if isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple):
        both = zip(target.elts, value.elts, strict=True)
        return {k: v for t, e in both for k, v in pairs(t, e, known).items()}
    if not isinstance(target, ast.Name):
        return {}
    if isinstance(value, ast.Tuple):
        found = {f"{target.id}[{i}]": text(e, known) for i, e in enumerate(value.elts)}
    else:
        found = {target.id: text(value, known)}
    return {name: t for name, t in found.items() if t is not None}


def names(source: str) -> dict[str, list[str]]:
    known: dict[str, str] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            known.update(pairs(node.targets[0], node.value, known))
    found: dict[str, list[str]] = {}
    for name, value in known.items():
        found.setdefault(value, []).append(name)
    return found


NAMES = names((Path(__file__).resolve().parents[2] / INSTALLED).read_text("utf-8"))


def check(path: Path, tree: ast.Module, source: str) -> list[tuple[int, str]]:
    if path.as_posix() == INSTALLED or path.name.endswith("_test.py"):
        return []
    texts = [n for n in ast.walk(tree) if isinstance(n, ast.Constant)]
    hits = [n for n in texts if isinstance(n.value, str) and n.value in NAMES]
    use = "the text of {} in ritmelli.machine.installed. Use the name."
    return [(n.lineno, use.format(" or ".join(NAMES[n.value]))) for n in hits]
