import ast
import re
import tokenize
from pathlib import Path

MESSAGE = "a comment. Say why in a name, a test, the PR or docs/."


def comment(token: tokenize.TokenInfo) -> bool:
    shebang = token.start == (1, 0) and token.string.startswith("#!")
    return token.type == tokenize.COMMENT and not shebang


def check(path: Path, _tree: ast.Module, source: str) -> list[tuple[int, str]]:
    lines = iter(re.split(r"(?<=\n)", source))
    tokens = tokenize.generate_tokens(lambda: next(lines, ""))
    found = [(token.start[0], MESSAGE) for token in tokens if comment(token)]
    return [] if path.is_relative_to("tools/lint/ruff") else found
