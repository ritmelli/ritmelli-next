import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ("src", "installer", "tools")
MESSAGE = "no code in the repo reads {}. Delete it, or add it with its reader."


def read_elsewhere(root: Path) -> set[str]:
    paths = list(root.glob("*.py"))
    for folder in FOLDERS:
        paths += (root / folder).rglob("*.py")
    names: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                names.update(alias.name for alias in node.names)
    return names


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
    _path: Path, tree: ast.Module, _source: str, read: set[str] = READ
) -> list[tuple[int, str]]:
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name)]
    known = read | {n.id for n in names if isinstance(n.ctx, ast.Load)}
    found = [pair for node in tree.body for pair in defined(node)]
    return [(line, MESSAGE.format(name)) for line, name in found if name not in known]
