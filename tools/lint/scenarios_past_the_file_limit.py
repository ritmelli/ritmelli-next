import ast
from pathlib import Path

COMMANDS = "src/ritmelli/features"
NOT_COMMANDS = ("state", "tuning")
VIEWS = ("items", "values")
MESSAGE = "{} scenarios, over {}. Cut a repeated one{}."
SPLIT = ", or move some to a test file next to it"


def limit(path: Path) -> int:
    name = path.name.removesuffix("_test.py")
    command = path.parent.parent.as_posix() == COMMANDS and name not in NOT_COMMANDS
    return 3 if command and not name.startswith("on_") else 6


def cases(node: ast.expr, names: dict[str, ast.expr]) -> int:
    if isinstance(node, ast.Name) and node.id in names:
        return cases(names[node.id], names)
    if isinstance(node, ast.Call) and ast.unparse(node.func) == "enumerate":
        return cases(node.args[0], names)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return cases(node.func.value, names) if node.func.attr in VIEWS else 1
    if isinstance(node, ast.Dict):
        return len(node.keys)
    return len(node.elts) if isinstance(node, ast.List | ast.Tuple) else 1


def parametrize(node: ast.expr, names: dict[str, ast.expr]) -> int:
    if isinstance(node, ast.Name) and node.id in names:
        node = names[node.id]
    if not isinstance(node, ast.Call):
        return 1
    marked = ast.unparse(node.func).endswith("mark.parametrize")
    return cases(node.args[1], names) if marked else 1


def scenarios(test: ast.FunctionDef, names: dict[str, ast.expr]) -> int:
    last, count = test.body[-1], 1
    if isinstance(last, ast.For) and isinstance(last.target, ast.Tuple):
        numbered = ast.unparse(last.iter).startswith("enumerate(")
        if not numbered or isinstance(last.target.elts[-1], ast.Tuple):
            count = cases(last.iter, names)
    for decorator in test.decorator_list:
        count *= parametrize(decorator, names)
    return count


def check(path: Path, tree: ast.Module, _source: str) -> list[tuple[int, str]]:
    if not path.name.endswith("_test.py"):
        return []
    assigned = [node for node in tree.body if isinstance(node, ast.Assign)]
    names = {
        t.id: n.value for n in assigned for t in n.targets if isinstance(t, ast.Name)
    }
    tests = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    count = sum(scenarios(n, names) for n in tests if n.name.startswith("test"))
    most = limit(path)
    split = SPLIT if most == 6 else ""
    return [(1, MESSAGE.format(count, most, split))] if count > most else []
