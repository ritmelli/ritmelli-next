import ast
import tokenize
from pathlib import Path

MESSAGE = "a comment. Say why in a name, a test, the PR or docs/."


def comment(token: tokenize.TokenInfo) -> bool:
    shebang = token.start == (1, 0) and token.string.startswith("#!")
    return token.type == tokenize.COMMENT and not shebang


def check(_path: Path, _tree: ast.Module, source: str) -> list[tuple[int, str]]:
    lines = iter(source.splitlines(keepends=True))
    tokens = tokenize.generate_tokens(lambda: next(lines, ""))
    return [(token.start[0], MESSAGE) for token in tokens if comment(token)]
