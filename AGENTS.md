# Agents

Before you write anything, say which kind of change it is: one entry of kinds.toml.
The first line of the PR body is `Kind: <name>`.
Every file the PR changes must match one of that kind's paths.
The Budget check enforces this with kinds.toml from the base branch.
The PR title follows "Its title" in CONTRIBUTING.md, and the Budget check enforces it.
If no kind fits, the change is core: stop and ask the owner. Write `Kind: core` only when the owner asked for the change.
After the first line, the body has up to 15 lines on what changes for the person using the app.

## House rules

- A PR changes at most 400 lines. uv.lock, src/ritmelli/storage/legacy/fixtures/, src/ritmelli/update/fixtures/, src/ritmelli/machine/fixtures/, ui/src/pixel/sheets/, filter/abi/ring.layout.json and the seven filter sources kept as in v0.7.0 (filter/apo/anel.h, filter/apo/voz.h, filter/apo/reamostra.h, filter/apo/micfx.cpp, filter/apo/voz.cpp, filter/apo/micfx.def, filter/apo/version.rc) do not count. Bigger: split it.
- At most 3 pushes after the PR opens. Past that, close it and start again with a smaller plan.
- A fix brings the input that failed, as a scenario next to the code.
- Tests sit next to the code: at most 3 scenarios per command, 6 per test file elsewhere. A new voice effect, source or piece brings none; the catalog conformance covers it.
- English everywhere, one name per concept, from GLOSSARY.md. No `utils.py`, `helpers.py`, `common/` or `Manager`. No date, round, PR number or song name in code. The exception is tools/lint/<name>_test.py: it cites the PRs of its occurrences as `#<n>`, and tools/lint/run.py requires it.
- No comment in Python: the why goes in a name, a test, the PR or docs/. The rule is tools/lint/no_comments.py.

## Where things live

```text
Command, or a rule of a command ............ src/ritmelli/features/<subject>/<command>.py
What happens when something finishes ....... src/ritmelli/features/<subject>/on_<event>.py
A rule shared by several commands .......... src/ritmelli/features/<subject>/ops/<operation>.py
A new side effect (file dialog, OS call) ... src/ritmelli/ports/<lib>/effects.py and run.py
Voice effect ............................... src/ritmelli/features/voice/effects/
Music source, YouTube fix .................. src/ritmelli/sources/
Screen piece, text, visual tweak ........... ui/src/pieces/
Where a piece sits on the screen ........... ui/src/layouts/
A tuned number ............................. the tuning.py next to the code that uses it
What is saved to disk ...................... src/ritmelli/storage/
CORE, owner only: kernel/, update/, machine/, storage/legacy/, filter/, installer/, .github/, tools/,
                  .claude/, sources/conformance.py, and every file at the root but pyproject.toml and uv.lock
```

## What to read first, after this file

- New command: the docstring of src/ritmelli/kernel/command.py, a neighbour command, the state.py of its feature.
- Rule of a command that exists: the command, the ops/ it calls, the state.py of each slice it crosses, the on_<event>.py files of its folder.
- Voice effect: a sibling effect and src/ritmelli/features/voice/effects/README.md.
- Screen piece: the piece and the header of ui/src/mirror.js.
- YouTube fix: the file in src/ritmelli/sources/youtube/ that the error points to.

## Core

Core is the CORE line above, and every path no other kind covers. Only the `core` kind covers it.
A core PR fails the Budget check on purpose. The owner merges it after its proof card, without reading the code. An agent never bypasses a check.
kernel/ stays under 900 lines.

If this file and the code disagree, the code wins.

## Proof

The proof of a PR is what its kind says in `proof`.
A verifier that did not write the code runs it and reports PASS or FAIL.
The merge queue takes only PASS.
The verifier's report, the proof card, sits under `## Proof` in the PR body and ends with `Verdict: PASS on <head>`.
The Budget check reads it on the current head: a push after the proof asks for the proof again.

## Findings

Look for the name before you record a finding: the same problem keeps the same name.
Record it after its command ran again and reproduced, with that output saved to a file.
Fill in the upper-case words. KIND is bug, leftover or rule. `--dry-run` prints what it would do and writes nothing.

```text
uv run python tools/finding.py list
uv run python tools/finding.py record --name NAME --kind KIND --pr N --file PATH --line N \
  --command "COMMAND" --output-file FILE
```

An issue with the label `promote` gets one PR that adds a lint rule and closes the issue.
An issue that also has `no-lint` gets no lint rule: it stays open, and REVIEW.md lists it.
A ready ruff rule comes first: its code in `select` in ruff.toml, and each occurrence in tools/lint/ruff/<CODE>/pr<n>.py.
With no ruff rule, write tools/lint/<name>.py and a <name>_test.py that cites both PRs.
CONTRIBUTING.md walks through a whole example.
