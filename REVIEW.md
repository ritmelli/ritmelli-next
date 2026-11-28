# Review

This file says when a review stops. Where another review rule disagrees, this file wins.

## Rounds

- Two rounds. Three when the PR touches core (see AGENTS.md).
- The second round reads only what changed since the first.

## Findings

- A finding blocks only with the command the reviewer ran and its output. Without them, it is dropped.
- An input that can only be built by hand does not block.
- It is one of three kinds: `bug` (a wrong result or a crash), `leftover` (something that does nothing now) or `rule` (a written rule broken, that no check catches yet).
- Before the fix, run the command again. A finding that does not reproduce is dropped.
- Personal taste is not a finding.
- Every finding that reproduced is recorded with `tools/finding.py record`, after its name is checked with `tools/finding.py list`.
- The fix for a finding changes a scenario of the command. It does not add one.
- A finding that was turned down does not come back without a new argument.
- The Mutation check changes each line the PR changed, one change at a time, and shows each change that no test next to the file caught. Each survivor gets the first answer that fits:
  1. The line does not need to exist: the code leaves.
  2. The test that should catch it is weak: that test is fixed, such as an `endswith` that takes any end becoming an exact comparison.
  3. A behavior has no test: a new scenario comes in, within the limits of AGENTS.md.
- A change that alters nothing the code does goes in `tools/mutation/equivalent.toml`: a `[[mutant]]` with the `file`, `function` and `change` the check printed, and `why`. The reviewer judges each entry.
- Run it on a commit with `uv run python tools/mutation/mutate.py $(git merge-base origin/main HEAD)`.

## Findings no lint rule catches

- `hand-rolled-library-call`: a loop or a walk that does what a library call already does (#34).
- `assert-repeats-earlier-check`: an `assert` or a check that repeats an earlier one (#37).
- `guard-for-hand-built-state`: a `try` or an `if` that guards a state only a hand-built input reaches (#46).
- `timeout-skips-the-restore`: a call that runs past its timeout and skips the step that puts the old state back (#43).
- `cut-missing-from-pr-body`: a port that leaves something out that the PR body does not list (#55).
- `comment-states-false-fact`: a comment that states something false, in a file that can have comments, such as a `.ps1`, `.iss` or `.yml` (#84).
- `doc-rule-the-check-refuses`: docs that teach something a check refuses (#97).
- `check-satisfied-by-generic-text`: a check that matches text so generic it passes without the thing it looks for (#111).

## What does not count

- No score from 0 to 10.
- No new verification tool in a PR.
- More test lines than product lines is a note for the reviewer, not a block.
