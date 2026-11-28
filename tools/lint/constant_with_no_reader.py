import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ("src", "installer", "tools")
CASES = Path("tools/lint/ruff")
MESSAGE = "no code in the repo reads {}. Delete it, or add it with its reader."


def last(name: str | None) -> str:
    return (name or "").split(".")[-1]


def module_reads(tree: ast.Module) -> set[tuple[str, str]]:
    imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]
    bound = {a.asname or a.name: last(a.name) for n in imports for a in n.names}
    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            found.add((bound.get(node.value.id, ""), node.attr))
        elif isinstance(node, ast.ImportFrom):
            found.update((last(node.module), alias.name) for alias in node.names)
    return found


def read_elsewhere(root: Path) -> set[tuple[str, str]]:
    paths = list(root.glob("*.py"))
    for folder in FOLDERS:
        paths += (root / folder).rglob("*.py")
    read: set[tuple[str, str]] = set()
    for path in [p for p in paths if not p.is_relative_to(root / CASES)]:
        read |= module_reads(ast.parse(path.read_text("utf-8")))
    return read


READ = read_elsewhere(ROOT)


def targets(node: ast.stmt) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        return node.targets
    return [node.target] if isinstance(node, ast.AnnAssign) else []


def defined(node: ast.stmt) -> list[tuple[int, str]]:
    if isinstance(node, ast.FunctionDef):
        return [] if node.name.startswith("test") else [(node.lineno, node.name)]
    names = [t for t in targets(node) if isinstance(t, ast.Name) and t.id.isupper()]
    return [(name.lineno, name.id) for name in names]


def check(
    path: Path, tree: ast.Module, _source: str, read: set[tuple[str, str]] = READ
) -> list[tuple[int, str]]:
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name)]
    known = {name for module, name in read if module == path.stem}
    known |= {n.id for n in names if isinstance(n.ctx, ast.Load)}
    body = [] if path.is_relative_to(CASES) else tree.body
    found = [pair for node in body for pair in defined(node)]
    return [(line, MESSAGE.format(name)) for line, name in found if name not in known]
