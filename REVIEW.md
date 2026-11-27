# Review

This file says when a review stops. Where another review rule disagrees, this file wins.

## Rounds

- Two rounds. Three when the PR touches core (see AGENTS.md).
- The second round reads only what changed since the first.

## Findings

- A finding blocks only with proof of use: an input that happened.
- Proof of use is a log line, a crash report, a counter from the app, a written usage script, or an item of the old app's list of what every theme covers.
- An input that can only be built by hand does not block.
- A finding without proof is dropped. It does not become an issue.
- The fix for a finding changes a scenario of the command. It does not add one.
- A finding that was turned down does not come back without a new argument.

## What does not count

- No score from 0 to 10.
- No new verification tool in a PR.
- More test lines than product lines is a note for the reviewer, not a block.
