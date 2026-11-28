"""Record a review finding as a GitHub issue. A second PR adds the label promote."""

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

EXAMPLE = """examples:
  uv run python tools/finding.py list
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
SHAPE = ".[] | {number, title, state, url: .html_url, labels: [.labels[].name]}"
NAME = "[a-z][a-z0-9-]{2,60}"
OCCURRENCE = re.compile(r"^<!-- occurrence pr=(\d+) ", re.MULTILINE)
LIMIT = 4000

Step = tuple[str, list[str]]


@dataclass(frozen=True)
class Issue:
    number: str
    title: str
    url: str
    open: bool
    labels: frozenset[str]
    prs: frozenset[int]
    occurrences: tuple[str, ...]


def valid_name(text: str) -> str:
    if not re.fullmatch(NAME, text):
        raise argparse.ArgumentTypeError(f"{text!r} does not match ^{NAME}$")
    return text


def read_output(path: str) -> str:
    try:
        data = Path(path).read_bytes()
        text = data.decode("utf-16" if data[:2] == b"\xff\xfe" else "utf-8", "replace")
    except OSError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if not text.strip():
        raise argparse.ArgumentTypeError(f"{path} is empty")
    return text[:LIMIT]


def parse(argv: list[str]) -> argparse.Namespace:
    text = {"epilog": EXAMPLE, "formatter_class": argparse.RawDescriptionHelpFormatter}
    top = argparse.ArgumentParser(description=__doc__, **text)
    actions = top.add_subparsers(dest="action", required=True)
    actions.add_parser("list", help="print the findings, promote first")
    parser = actions.add_parser("record", help="record one occurrence", **text)
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
    return top.parse_args(argv)


def note(args: argparse.Namespace) -> str:
    text = f"$ {args.ran}\n{args.output.rstrip()}"
    fence = "`" * max([3, *(len(run) + 1 for run in re.findall("`+", text))])
    machine = f"pr={args.pr} file={args.file} line={args.line} kind={args.kind}"
    where = f"Found in #{args.pr} at `{args.file}:{args.line}` ({args.kind}):"
    return f"<!-- occurrence {machine} -->\n{where}\n\n{fence}\n{text}\n{fence}\n"


def listed(gh: Callable[..., str]) -> list[dict[str, Any]]:
    found = gh("api", ISSUES, "--paginate", "--jq", SHAPE)
    items = [json.loads(line) for line in found.splitlines()]
    return sorted(items, key=lambda item: item["number"])


def read(gh: Callable[..., str], item: dict[str, Any]) -> Issue:
    number, title, url = str(item["number"]), item["title"], item["url"]
    view = json.loads(gh("issue", "view", number, "--json", "body,comments"))
    texts = [view["body"], *(comment["body"] for comment in view["comments"])]
    prs = frozenset(int(n) for text in texts for n in OCCURRENCE.findall(text))
    found = tuple(text[m.start() :] for text in texts if (m := OCCURRENCE.search(text)))
    labels = frozenset(item["labels"])
    return Issue(number, title, url, item["state"] == "open", labels, prs, found)


def find(gh: Callable[..., str], name: str) -> list[Issue]:
    """The issues with the title, lowest number first.

    GitHub lists a new issue only seconds later, so two records of a new name can
    each create one. The lowest number is the finding; the others are its twins.
    """
    title = f"finding: {name}"
    return [read(gh, item) for item in listed(gh) if item["title"] == title]


def table(gh: Callable[..., str]) -> list[str]:
    groups: dict[str, list[Issue]] = {}
    for item in listed(gh):
        groups.setdefault(item["title"], []).append(read(gh, item))
    issues = [
        replace(group[0], prs=frozenset(pr for each in group for pr in each.prs))
        for group in groups.values()
    ]
    lines: list[str] = []
    for issue in sorted(issues, key=lambda i: ("promote" not in i.labels, i.title)):
        count = f"{len(issue.prs)} PR" + "s" * (len(issue.prs) != 1)
        labels = sorted(issue.labels & {"promote", "rule-missed"})
        name = issue.title.removeprefix("finding: ")
        lines.append("  ".join([name, count, *labels, issue.url]))
    return lines or ["no findings yet"]


def plan(name: str, pr: int, occurrence: str, issues: list[Issue]) -> list[Step]:
    title = f"finding: {name}"
    if not issues:
        create = ["issue", "create", "--title", title, "--label", "finding"]
        return [(f"create issue {title}", [*create, "--body", INTRO + occurrence])]
    issue, *twins = issues
    number = issue.number
    steps: list[Step] = []
    if not issue.open:
        steps.append((f"reopen issue #{number}", ["issue", "reopen", number]))
    comment = ["issue", "comment", number, "--body", occurrence]
    steps.append((f"comment on issue #{number}", comment))
    have = {text.splitlines()[0] for text in (*issue.occurrences, occurrence)}
    for twin in twins:
        other = twin.number
        for text in twin.occurrences:
            if (marker := text.splitlines()[0]) not in have:
                have.add(marker)
                where = f"{marker.strip('<!-> ')} of issue #{other}"
                copy = ["issue", "comment", number, "--body", text]
                steps.append((f"copy {where} to issue #{number}", copy))
        duplicate = ["issue", "comment", other, "--body", f"Duplicate of #{number}"]
        close = ["issue", "close", other, "--reason", "not planned"]
        unlabel = ["issue", "edit", other, "--remove-label", "finding"]
        steps.append((f"comment Duplicate of #{number} on issue #{other}", duplicate))
        steps.append((f"close issue #{other}", close))
        steps.append((f"remove label finding from issue #{other}", unlabel))
    prs = {pr, *(n for each in issues for n in each.prs)}
    due = {"rule-missed": not issue.open, "promote": len(prs) >= 2}
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
    if args.action == "list":
        print(*table(gh), sep="\n")
        return 0
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
