import codecs
import re
import subprocess
import sys
from collections.abc import Callable, Iterator

SPAN = re.compile(r"`([^`]+)`")
CITATION = re.compile(r"([\w./-]*\.[A-Za-z]\w*):([1-9]\d*)(?:-([1-9]\d*))?")
OTHER_TREE = re.compile(r"\s+(?:of|at)\s+`")
UNCHECKED = ("## Proof", "## Review")


def citations(body: str) -> Iterator[tuple[int, str, str, int]]:
    checked = True
    for number, line in enumerate(body.replace("\r", "").split("\n"), 1):
        if line.startswith("## "):
            checked = line not in UNCHECKED
        if not checked:
            continue
        for span in SPAN.finditer(line):
            cited = CITATION.fullmatch(span[1])
            if cited and not OTHER_TREE.match(line, span.end()):
                path, first, last = cited.groups()
                yield number, span[1], path, int(last or first)


def wrong(body: str, names: list[str], length: Callable[[str], int]) -> list[str]:
    found: list[str] = []
    for number, text, path, last in citations(body):
        files = [name for name in names if name == path or name.endswith(f"/{path}")]
        lines = max(map(length, files), default=0)
        if not files:
            found.append(f"line {number}: {text}: no such file at the head")
        elif last > lines:
            found.append(f"line {number}: {text}: the file has {lines} lines")
    return found


def lines(data: bytes) -> int:
    if data.startswith(codecs.BOM_UTF16_LE):
        data = data.decode("utf-16").encode()
    return len(data.splitlines())


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def main(head: str) -> int:
    def length(name: str) -> int:
        return lines(git("show", f"{head}:{name}"))

    names = git("ls-tree", "-r", "--name-only", head).decode().splitlines()
    found = wrong(sys.stdin.buffer.read().decode(), names, length)
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
