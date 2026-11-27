# Agents

Before you write anything, say which ficha the change is: one entry of fichas.toml.
The first line of the PR body is `Ficha: <name>`.
Every file the PR changes must match one of that ficha's paths.
The Budget check enforces this with fichas.toml from the base branch.
If no ficha fits, the change is core: stop and ask the owner. Write `Ficha: core` only when the owner asked for the change.
After the first line, the body has up to 15 lines on what changes for the person using the app.

## House rules

- A PR changes at most 400 lines. uv.lock, fixtures, pixel sheets and ring.layout.json do not count. Bigger: split it.
- At most 3 pushes after the PR opens. Past that, close it and start again with a smaller plan.
- A fix brings the input that failed, as a scenario next to the code.
- Tests sit next to the code: at most 3 scenarios per command, 6 per test file elsewhere. A new voice effect, source or piece brings none; the catalog conformance covers it.
- English everywhere, one name per concept, from GLOSSARY.md. No `utils.py`, `helpers.py`, `common/` or `Manager`. No date, round, PR number or song name in code.

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

Core is the CORE line above, and every path no other ficha covers. Only the `core` ficha covers it.
Paths in .github/CODEOWNERS also need the owner's approval, given on the evidence card, not on the code.
kernel/ stays under 900 lines.

If this file and the code disagree, the code wins.

## Proof

The proof of a PR is what its ficha says in `proof`.
A verifier that did not write the code runs it and reports PASS or FAIL.
The merge queue takes only PASS.
