import ast
from pathlib import Path

LITERALS = (ast.Tuple, ast.List, ast.Set)
MESSAGE = "a literal starred inside a literal. Write its items directly."


def starred(node: ast.AST) -> bool:
    if not isinstance(node, LITERALS):
        return False
    stars = [item for item in node.elts if isinstance(item, ast.Starred)]
    return any(isinstance(star.value, LITERALS) for star in stars)


def check(path: Path, tree: ast.Module, source: str) -> list[tuple[int, str]]:
    return [(node.lineno, MESSAGE) for node in ast.walk(tree) if starred(node)]
