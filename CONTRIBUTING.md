# Contributing

This file takes a change from a clone to a merge. AGENTS.md has the house rules and where each thing lives.
REVIEW.md has the review rules. If this file and the code disagree, the code wins.

## Set up and run the Check

You need git and [uv](https://docs.astral.sh/uv/). The Check uses uv 0.12.15. uv brings Python 3.12.
The finding commands also need [gh](https://cli.github.com/), logged in with `gh auth login`.
The blocks here are for a POSIX shell. On Windows, use Git Bash.

```sh
git clone https://github.com/ritmelli/ritmelli-next.git
cd ritmelli-next
uv sync --locked
```

The Check runs these on every PR, in this order. Run them before each push:

```sh
uv run ruff check --ignore-noqa
uv run ruff format --check
uv run pyright
uv run lint-imports
uv run python tools/check_layout.py
uv run python tools/lint/run.py
uv run pytest
```

`--ignore-noqa` means a `# noqa` comment silences nothing. Fix the code instead.
The Check also runs actionlint on `.github/workflows/`.

## A PR

### Its kind

The first line of the PR body is `Kind: <name>`, one entry of `kinds.toml`.
Every file the PR changes must match a path of that kind.
The Budget check reads `kinds.toml` from the base branch.
After the first line, up to 15 lines say what changes for the person using the app.

| Kind | For | Paths |
|---|---|---|
| `command` | A command, new or changed, and its button | `src/ritmelli/features/**`, `ui/src/pieces/**` |
| `io-command` | A command whose reply waits for I/O | `src/ritmelli/features/**` |
| `shared-rule` | A rule that several commands use | `src/ritmelli/features/**` |
| `port` | A new side effect at the edge | `src/ritmelli/ports/**`, `pyproject.toml`, `uv.lock` |
| `voice-effect` | A voice effect, new or tuned | `src/ritmelli/features/voice/effects/**` |
| `source` | A new music source | `src/ritmelli/sources/*/**`, `src/ritmelli/features/**`, `ui/src/pieces/**`, `pyproject.toml`, `uv.lock` |
| `youtube` | A YouTube fix | `src/ritmelli/sources/youtube/**`, `pyproject.toml`, `uv.lock` |
| `theme` | A visual tweak to a screen piece | `ui/src/pieces/**`, `ui/src/pixel/**` |
| `piece` | A new screen piece and its place | `ui/src/pieces/**`, `ui/src/layouts/**`, `ui/src/pixel/**` |
| `tuning` | A tuned number | `src/ritmelli/features/**/tuning.py`, `src/ritmelli/audio/**/tuning.py` |
| `setting` | A new preference that is saved | `src/ritmelli/features/**/state.py`, `src/ritmelli/storage/settings.py` |
| `sound` | A feature that crosses the sound path | `src/ritmelli/audio/**`, `src/ritmelli/features/**`, `src/ritmelli/storage/settings.py`, `ui/src/pieces/**` |
| `core` | A core change the owner asked for | everything |

### Its size

- At most 400 changed lines, added plus removed. `uv.lock` and the fixtures and files AGENTS.md lists do not count.
  Bigger: split it.
- At most 3 pushes after the PR opens. Past that, close it and start again with a smaller plan.

The Budget check counts both.

### Core

Core is `kernel/`, `update/`, `machine/`, `storage/legacy/`, `filter/`, `installer/`, `.github/`, `tools/`,
`.claude/`, `sources/conformance.py`, every file at the root but `pyproject.toml` and `uv.lock`, and every path no
other kind covers. Only the `core` kind covers it.

It is what the rest stands on: the update and the installer that reach each PC, the filter on the microphone, the
kernel, and the checks themselves. A mistake there reaches every PC that updates, or lets the next PRs through. So
only the owner merges it.

Write `Kind: core` only when the owner asked for the change. If your change is core and nobody asked, open an issue
first. A core PR fails the Budget check on purpose. The owner merges it after its proof card.

### Its proof

Each kind has a `proof` in `kinds.toml`: what to run to show that the change works.
Someone who did not write the code runs it and reports PASS or FAIL in the PR, with each command and what it printed.
That report is the proof card. The merge queue takes only PASS.
The card sits under `## Proof` in the PR body and ends with the line `Verdict: PASS on <head>`. The Budget check reads
that line on the current head, so a push after the proof asks for the proof again.

## Review

A review runs in rounds: two, three when the PR touches core. REVIEW.md has the rules. In short:

- A finding brings the command the reviewer ran and its output.
- A finding is one of three kinds:
  - `bug`: the code does the wrong thing. The command shows the input and the wrong result, or the crash.
  - `leftover`: something that does nothing now: dead code, a flag nobody reads, a line left commented out.
  - `rule`: a rule written in AGENTS.md or GLOSSARY.md is broken, and no check catches it yet.
- Before the fix, the author runs the command again. A finding that does not reproduce is dropped.
- Personal taste is not a finding. A name or an order you like better is none of the three kinds.
- A finding that was turned down does not come back without a new argument.
- Every finding that reproduced is recorded, as the next section shows.

## Findings

A problem that a review finds is kept as a GitHub issue. When a second PR has it, it becomes a lint rule.
The lint runs in seconds, before any review, and spares the review what it already catches.
A rule enters only with two real cases, so the lint grows with the problems that happened.

Each finding is one issue titled `finding: <name>`, with the label `finding`. Only `tools/finding.py` writes it.
Each occurrence adds the PR, the file, the line, the command and its output.
When a second PR has the same finding, the script adds the label `promote`.

### An example, start to end

The PRs, the issue numbers and the code here are made up. The commands run: try them in a scratch clone.
`--dry-run` reads GitHub and prints what the script would do. It writes nothing.

**1. Look for the name.** The same problem needs the same name, or the count never reaches two.

```sh
uv run python tools/finding.py list
```

With no findings yet, it prints `no findings yet`. Otherwise it prints one line per finding: its name, how many PRs
had it, its labels and its address. The ones with `promote` come first.

**2. The first occurrence.** Say the review of #31 finds a line left commented out. These lines plant it, save what
the check prints (ruff exits with 1: it found it), and record it:

```sh
printf 'def stop(grace: float) -> float:\n    # grace = 0.5\n    return grace\n' > src/ritmelli/ports/process/stop.py
uv run ruff check --select ERA001 src/ritmelli/ports/process/stop.py > pr31.txt
uv run python tools/finding.py record --name commented-out-code --kind leftover --pr 31 \
  --file src/ritmelli/ports/process/stop.py --line 2 \
  --command "uv run ruff check --select ERA001 src/ritmelli/ports/process/stop.py" \
  --output-file pr31.txt --dry-run
```

```text
would ensure labels finding, promote, rule-missed
would create issue finding: commented-out-code
```

Without `--dry-run`, it creates the issue, say #41. The author of #31 runs the command again and removes the line.

**3. The second occurrence, in another PR.** The review of #34 finds the same problem:

```sh
printf 'def again(tries: int) -> int:\n    # print(tries)\n    return tries + 1\n' > src/ritmelli/update/retry.py
uv run ruff check --select ERA001 src/ritmelli/update/retry.py > pr34.txt
uv run python tools/finding.py record --name commented-out-code --kind leftover --pr 34 \
  --file src/ritmelli/update/retry.py --line 2 \
  --command "uv run ruff check --select ERA001 src/ritmelli/update/retry.py" \
  --output-file pr34.txt --dry-run
```

Once #41 exists, this finds it. It would comment the occurrence on #41 and add the label `promote`: two PRs had it.
The same PR twice counts once. Here no #41 exists on GitHub, so the dry run says `would create issue` again.

**4. The rule, from ruff.** An issue with `promote` becomes one PR that adds a lint rule and closes the issue.
Look for a ready ruff rule first. Here ruff has one, `ERA001`. Each real occurrence becomes a case, named for its PR:

```sh
mkdir -p tools/lint/ruff/ERA001
mv src/ritmelli/ports/process/stop.py tools/lint/ruff/ERA001/pr31.py
mv src/ritmelli/update/retry.py tools/lint/ruff/ERA001/pr34.py
```

Then add `"ERA001"` at the end of `select` in `ruff.toml`. `tools/lint/ruff_cases_test.py` runs ruff on each case,
and wants a flag on each one, from two PRs or more:

```sh
uv run pytest tools/lint/ruff_cases_test.py
uv run ruff check --ignore-noqa
```

The test passes, and ruff prints `All checks passed!`. The PR body starts with `Kind: core` and says `Closes #41`,
so the merge closes the issue.

**5. A rule of ours, when ruff has none.** Say `finding: manager-class` got `promote` from #36 and #39: two classes
with `Manager` in the name, which AGENTS.md bans. A rule of ours is `tools/lint/<name>.py`, the issue name with `_` for
`-`. Its `check(path, tree, source)` gets the path from the repository root and the `ast` of the source. It returns
`(line, message)` pairs. Its test, `<name>_test.py`, holds the real occurrences and cites each PR as `#<n>`:

```sh
cat > tools/lint/manager_class.py <<'EOF'
import ast


def check(path, tree, source):
    names = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    return [(n.lineno, "a Manager class") for n in names if "Manager" in n.name]
EOF
cat > tools/lint/manager_class_test.py <<'EOF'
import ast
from pathlib import Path

import manager_class

CASES = {
    "#36": "class DeckManager:\n    pass\n",
    "#39": "class ShelfManager(dict):\n    pass\n",
}


def test_it_flags_each_occurrence() -> None:
    for pr, source in CASES.items():
        assert manager_class.check(Path("src/a.py"), ast.parse(source), source), pr
EOF
uv run pytest tools/lint/manager_class_test.py
uv run python tools/lint/run.py
```

The test passes. `run.py` prints nothing, because no class in the repo breaks the rule. On a hit, it prints
`<file>:<line>: manager-class: a Manager class` and exits with 1, so the Check fails.

**6. What `run.py` refuses.** Before any rule runs, `run.py` checks each one. It prints why, runs no rule, and exits
with 1 when a rule:

- has no test: `tools/lint/manager_class.py: no tools/lint/manager_class_test.py. Test it on its occurrences.`
- has a test that cites fewer than two PRs:
  `tools/lint/manager_class_test.py: cites fewer than two PRs. Cite each as #<n>.`
- is over 60 lines: `tools/lint/manager_class.py: 61 lines, over 60.`
- imports anything but `ast`, `collections`, `dataclasses`, `pathlib`, `re`, `tokenize` and `typing`:
  `tools/lint/manager_class.py: imports os. A rule imports only ast, collections, dataclasses, pathlib, re, tokenize, typing.`

A rule stays small, and reads code only through Python's own `ast`: no parser of ours, no library from outside.
Take the test away to see the first refusal:

```sh
rm tools/lint/manager_class_test.py
uv run python tools/lint/run.py
```

**7. The problem comes back.** The merge closed the issue. If a review finds the problem again, `record` reopens the
issue, comments the occurrence and adds the label `rule-missed`: the rule let it through. Say #45 adds
`class deck_manager:`. The PR that answers adds it to `CASES` as `"#45"`, widens the check to
`"manager" in n.name.lower()`, and closes the issue again. When a ruff rule cannot see the new case, the answer is a
rule of ours.

**8. A rule becomes architecture.** The owner reads the lint rules from time to time and decides which ones become
structure. That is the owner's call, not a PR's. In this repo, structure looks like the `subprocess` contract in
`.importlinter`. A rule that looks for `import subprocess` outside `ports/process/` finds each import, line by line.
The contract states the boundary itself: `uv run lint-imports` fails when any module of the package but
`ritmelli.ports.process` imports `subprocess`. With the contract in place, the rule goes.

**9. No rule can see it.** Some findings need judgment, and no lint rule can tell them from good code. The owner
gives such an issue the label `no-lint` and a line under "Findings no lint rule catches" in REVIEW.md, where the
review looks for it. The issue stays open, and `record` keeps adding the occurrences to it.
