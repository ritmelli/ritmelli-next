import ast
from pathlib import Path

MESSAGE = "constants packed in one assignment. Write one constant per line."


def names(target: ast.expr, count: int) -> bool:
    if not isinstance(target, ast.Tuple | ast.List) or len(target.elts) != count:
        return False
    return all(isinstance(item, ast.Name) for item in target.elts)


def packed(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Tuple):
        return False
    return any(names(target, len(node.value.elts)) for target in node.targets)


def check(_path: Path, tree: ast.Module, _source: str) -> list[tuple[int, str]]:
    return [(node.lineno, MESSAGE) for node in tree.body if packed(node)]
