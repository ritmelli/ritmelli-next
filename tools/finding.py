"""Record a review finding as a GitHub issue. A second PR adds the label promote."""

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

EXAMPLE = """example:
  uv run python tools/finding.py record --name redundant-process-flag --kind leftover \\
    --pr 123 --file src/ritmelli/ports/process/run.py --line 40 \\
    --command "uv run ruff check" --output-file ruff.txt --dry-run
"""
GUIDE = "https://github.com/ritmelli/ritmelli-next/blob/main/CONTRIBUTING.md#findings"
INTRO = f"""A problem that reviews found, recorded by `tools/finding.py`, one PR per \
occurrence. When a second PR has it, the issue gets the label `promote` and the \
problem becomes a lint rule. See [Findings]({GUIDE}).

"""
LABELS = {
    "finding": ("d93f0b", "A problem a review found"),
    "promote": ("0e8a16", "In two PRs: make it a lint rule"),
    "rule-missed": ("b60205", "Its lint rule let it through"),
}
ISSUES = "repos/{owner}/{repo}/issues?labels=finding&state=all&per_page=100"
SHAPE = ".[] | {number, title, state, labels: [.labels[].name]}"
NAME = "[a-z][a-z0-9-]{2,60}"
OCCURRENCE = re.compile(r"^<!-- occurrence pr=(\d+) ", re.MULTILINE)
LIMIT = 4000

Step = tuple[str, list[str]]


@dataclass(frozen=True)
class Issue:
    number: str
    open: bool
    labels: frozenset[str]
    prs: frozenset[int]


def valid_name(text: str) -> str:
    if not re.fullmatch(NAME, text):
        raise argparse.ArgumentTypeError(f"{text!r} does not match ^{NAME}$")
    return text


def read_output(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if not text.strip():
        raise argparse.ArgumentTypeError(f"{path} is empty")
    return text[:LIMIT]


def parse(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EXAMPLE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("action", choices=["record"], metavar="record")
    parser.add_argument("--name", type=valid_name, required=True)
    parser.add_argument("--kind", choices=["bug", "leftover", "rule"], required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--line", type=int, required=True)
    parser.add_argument("--command", dest="ran", metavar="COMMAND", required=True)
    parser.add_argument(
        "--output-file", dest="output", metavar="FILE", type=read_output, required=True
    )
    parser.add_argument("--dry-run", action="store_true", help="read and print only")
    return parser.parse_args(argv)


def note(args: argparse.Namespace) -> str:
    text = f"$ {args.ran}\n{args.output.rstrip()}"
    fence = "`" * max([3, *(len(run) + 1 for run in re.findall("`+", text))])
    machine = f"pr={args.pr} file={args.file} line={args.line} kind={args.kind}"
    where = f"Found in #{args.pr} at `{args.file}:{args.line}` ({args.kind}):"
    return f"<!-- occurrence {machine} -->\n{where}\n\n{fence}\n{text}\n{fence}\n"


def find(gh: Callable[..., str], name: str) -> Issue | None:
    listed = gh("api", ISSUES, "--paginate", "--jq", SHAPE)
    for item in map(json.loads, listed.splitlines()):
        if item["title"] == f"finding: {name}":
            number = str(item["number"])
            view = json.loads(gh("issue", "view", number, "--json", "body,comments"))
            texts = [view["body"], *(comment["body"] for comment in view["comments"])]
            prs = frozenset(int(n) for text in texts for n in OCCURRENCE.findall(text))
            labels = frozenset(item["labels"])
            return Issue(number, item["state"] == "open", labels, prs)
    return None


def plan(name: str, pr: int, occurrence: str, issue: Issue | None) -> list[Step]:
    title = f"finding: {name}"
    if issue is None:
        create = ["issue", "create", "--title", title, "--label", "finding"]
        return [(f"create issue {title}", [*create, "--body", INTRO + occurrence])]
    number = issue.number
    steps: list[Step] = []
    if not issue.open:
        steps.append((f"reopen issue #{number}", ["issue", "reopen", number]))
    comment = ["issue", "comment", number, "--body", occurrence]
    steps.append((f"comment on issue #{number}", comment))
    due = {"rule-missed": not issue.open, "promote": len(issue.prs | {pr}) >= 2}
    for label, now in due.items():
        if now and label not in issue.labels:
            edit = ["issue", "edit", number, "--add-label", label]
            steps.append((f"add label {label} to issue #{number}", edit))
    return steps


def run_gh(*args: str) -> str:
    done = subprocess.run(["gh", *args], stdout=subprocess.PIPE, encoding="utf-8")
    done.check_returncode()
    return done.stdout


def main(argv: list[str], gh: Callable[..., str] = run_gh) -> int:
    args = parse(argv)
    steps = plan(args.name, args.pr, note(args), find(gh, args.name))
    if args.dry_run:
        print(f"would ensure labels {', '.join(LABELS)}")
        for text, _ in steps:
            print(f"would {text}")
        return 0
    for label, (color, about) in LABELS.items():
        gh("label", "create", label, "--force", "-c", color, "-d", about)
    for text, step in steps:
        print(text, gh(*step).strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
