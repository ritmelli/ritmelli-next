import ast
import copy
import re
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from fnmatch import fnmatchcase
from pathlib import Path

LEFT_OUT = ("*_test.py", "*_measure.py", "conftest.py", "tools/lint/ruff/*")
PAIRS = (
    (ast.Lt, ast.LtE),
    (ast.Gt, ast.GtE),
    (ast.Eq, ast.NotEq),
    (ast.In, ast.NotIn),
    (ast.Is, ast.IsNot),
)
SWAP = {**dict(PAIRS), **{b: a for a, b in PAIRS}}
NO_CONTEXT = ast.parse("__import__('contextlib').nullcontext()", mode="eval").body
Site = tuple[str, ast.AST, str, ast.AST]


def changed(root: Path, base: str) -> dict[str, set[int]]:
    git = ["git", "diff", "-U0", "--no-prefix", "--diff-filter=d", base, "--", "*.py"]
    diff = subprocess.run(
        git, cwd=root, capture_output=True, encoding="utf-8", check=True
    )
    lines: dict[str, set[int]] = {}
    for text in diff.stdout.splitlines():
        if text.startswith("+++ "):
            current = lines.setdefault(text[4:], set())
        elif hunk := re.match(r"@@ -\S+ \+(\d+),?(\d*)", text):
            start = int(hunk[1])
            current.update(range(start, start + int(hunk[2] or 1)))
    return {
        path: numbers
        for path, numbers in lines.items()
        if not any(fnmatchcase(path, pattern) for pattern in LEFT_OUT)
    }


def sites(node: ast.AST, function: str) -> Iterator[Site]:
    for field, value in ast.iter_fields(node):
        for child in value if isinstance(value, list) else [value]:
            if isinstance(child, ast.AST):
                yield function, node, field, child
                named = isinstance(child, ast.FunctionDef | ast.ClassDef)
                inner = f"{function}.{child.name}" if named else function
                yield from sites(child, inner.removeprefix("<module>."))


def removals(parent: ast.AST, field: str, node: ast.AST) -> Iterator[ast.AST]:
    bare = isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    simple = isinstance(node, ast.stmt) and not hasattr(node, "body")
    if simple and not bare and not isinstance(node, ast.Pass):
        yield ast.Pass()
    if isinstance(parent, ast.withitem) and field == "context_expr":
        if not parent.optional_vars:
            yield NO_CONTEXT
    if isinstance(parent, ast.ExceptHandler) and field == "type":
        yield ast.Tuple([], ast.Load())


def swaps(node: ast.AST, lines: set[int]) -> Iterator[ast.AST]:
    if isinstance(node, ast.Compare):
        for i, op in enumerate(node.ops):
            ops = [*node.ops[:i], SWAP[type(op)](), *node.ops[i + 1 :]]
            yield ast.Compare(node.left, ops, node.comparators)
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        yield ast.Constant(not node.value)
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        if all(isinstance(element, ast.Constant) for element in node.elts):
            for i, element in enumerate(node.elts):
                if element.lineno in lines:
                    smaller = copy.copy(node)
                    smaller.elts = [*node.elts[:i], *node.elts[i + 1 :]]
                    yield smaller


def mutant(source: bytes, node: ast.AST, new: str) -> bytes:
    lines = source.splitlines(keepends=True)
    start = sum(map(len, lines[: node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[: node.end_lineno - 1])) + node.end_col_offset
    return source[:start] + new.encode() + source[end:]


def passes(root: Path, tests: list[Path]) -> bool:
    pytest = [sys.executable, "-B", "-m", "pytest", "-x", *tests]
    return (
        not tests
        or subprocess.run(pytest, cwd=root, capture_output=True).returncode == 0
    )


def survivors(
    root: Path, path: str, lines: set[int], equivalent: set[tuple[str, str, str]]
) -> list[str]:
    file = root / path
    source = file.read_bytes()
    tests = sorted([*file.parent.glob("*_test.py"), *file.parent.glob("*_measure.py")])
    if not passes(root, tests):
        return [f"{path}: the tests next to it fail with no change"]
    found: list[str] = []
    try:
        for function, parent, field, node in sites(ast.parse(source), "<module>"):
            made = [*removals(parent, field, node), *swaps(node, lines)]
            for new in map(ast.unparse, made):
                change = f"{ast.unparse(node)} -> {new}"
                touched = lines & set(range(node.lineno, node.end_lineno + 1))
                if touched and (path, function, change) not in equivalent:
                    file.write_bytes(mutant(source, node, new))
                    if passes(root, tests):
                        found.append(f"{path}:{node.lineno}: {function}: {change}")
    finally:
        file.write_bytes(source)
    return found


def main(root: Path, base: str) -> int:
    listed = (root / "tools" / "mutation" / "equivalent.toml").read_text("utf-8")
    mutants = tomllib.loads(listed).get("mutant", [])
    equivalent = {(m["file"], m["function"], m["change"]) for m in mutants}
    found = [
        line
        for path, numbers in changed(root, base).items()
        for line in survivors(root, path, numbers, equivalent)
    ]
    sys.stdout.buffer.write("".join(f"{line}\n" for line in found).encode())
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(Path.cwd(), sys.argv[1]))
