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

## Findings no lint rule catches

Each of these came up in two PRs or more. They need judgment, so no lint rule checks them: the review looks for them.

- `hand-rolled-library-call`: a loop or a walk that does what a library call already does (#34).
- `assert-repeats-earlier-check`: an `assert` or a check that repeats an earlier one (#37).
- `guard-for-hand-built-state`: a `try` or an `if` that guards a state only a hand-built input reaches (#46).

## What does not count

- No score from 0 to 10.
- No new verification tool in a PR.
- More test lines than product lines is a note for the reviewer, not a block.
