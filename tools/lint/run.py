"""Check our lint rules, then run each one on src/, installer/ and tools/.

A rule is tools/lint/<name>.py with check(path, tree, source) -> [(line, message)].
The path is relative to the repository root; the tree is the ast of the source."""

import ast
import re
import runpy
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ("src", "installer", "tools")
MODULES = {"ast", "re", "tokenize", "pathlib", "dataclasses", "typing", "collections"}
MAX_LINES = 60

Check = Callable[[Path, ast.Module, str], list[tuple[int, str]]]


def rules(lint: Path) -> list[Path]:
    paths = sorted(lint.glob("*.py"))
    return [p for p in paths if p.name != "run.py" and not p.stem.endswith("_test")]


def imported(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append("." * node.level + (node.module or ""))
    return names


def refusals(rule: Path) -> list[str]:
    where, test = f"tools/lint/{rule.name}", rule.with_name(f"{rule.stem}_test.py")
    found: list[str] = []
    if not test.exists():
        found.append(f"{where}: no tools/lint/{test.name}. Test it on its occurrences.")
    elif len(set(re.findall(r"#(\d+)", test.read_text(encoding="utf-8")))) < 2:
        found.append(
            f"tools/lint/{test.name}: cites fewer than two PRs. Cite each as #<n>."
        )
    source = rule.read_text(encoding="utf-8")
    if (lines := len(source.splitlines())) > MAX_LINES:
        found.append(f"{where}: {lines} lines, over {MAX_LINES}.")
    for name in imported(ast.parse(source)):
        if name.split(".")[0] not in MODULES:
            allowed = ", ".join(sorted(MODULES))
            found.append(f"{where}: imports {name}. A rule imports only {allowed}.")
    return found


def hits(root: Path, checks: dict[str, Check]) -> list[str]:
    found: list[str] = []
    for path in sorted(p for f in FOLDERS for p in (root / f).rglob("*.py")):
        where = path.relative_to(root)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(where))
        for name, check in checks.items():
            for line, message in check(where, tree, source):
                found.append(f"{where.as_posix()}:{line}: {name}: {message}")
    return found


def main(root: Path) -> int:
    lint = root / "tools" / "lint"
    found = [line for rule in rules(lint) for line in refusals(rule)]
    if not found:
        loaded = {r.stem.replace("_", "-"): runpy.run_path(str(r)) for r in rules(lint)}
        found = hits(root, {name: rule["check"] for name, rule in loaded.items()})
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(ROOT))
