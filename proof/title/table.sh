# usage: bash table.sh <title.sh>; each row: expect|title  (expect = pass, format, period, length)
script=$1
work=$(mktemp -d); cd "$work" || exit 9
p100="feat(installer): $(printf 'a%.0s' $(seq 1 83))"
p101="feat(installer): $(printf 'a%.0s' $(seq 1 84))"
rows=()
for t in build chore ci docs feat fix perf refactor revert style test; do
  rows+=("pass|$t: port the silent device check" "pass|$t(machine): port the silent device check")
done
rows+=(
  "pass|fix(web,mobile): new threads no longer spike CPU"
  "pass|fix(machine,update,ui-2): three scopes with a digit and a dash"
  "pass|feat(update)!: drop the old manifest field"
  "pass|feat!: drop the old manifest field"
  "pass|$p100"
  "pass|ci(budget): check the PR title and write down the PR rules"
  "format|port the silent device check"
  "format|: port the silent device check"
  "format|feature(machine): port the silent device check"
  "format|wip: port the silent device check"
  "format|Fix(installer): the build stops"
  "format|FEAT: port the silent device check"
  "format|fix(Installer): the build stops"
  "format|fix(installer):the build stops"
  "format|fix(installer): The build stops"
  "period|fix(installer): the build stops."
  "length|$p101"
  'pass|fix: run $(touch pwned) and `touch pwned2` as text'
  'format|Fix: run $(touch pwned) and `touch pwned2` as text'
  'period|fix(ui): run $(touch pwned) `touch pwned2`.'
)
fails=0
for row in "${rows[@]}"; do
  want=${row%%|*}; t=${row#*|}
  out=$(TITLE="$t" bash --noprofile --norc -eo pipefail "$script" 2>&1); code=$?
  case $want in
    pass) ok=$([ $code = 0 ] && [ -z "$out" ] && echo y);;
    format) ok=$([ $code = 1 ] && [[ $out == "::error::the PR title must be '<type>(<scope>): <description>'"* ]] && echo y);;
    period) ok=$([ $code = 1 ] && [ "$out" = "::error::the PR title must not end with a period: drop it" ] && echo y);;
    length) ok=$([ $code = 1 ] && [ "$out" = "::error::shorten the PR title (${#t} characters, the limit is 100)" ] && echo y);;
  esac
  [ "$ok" = y ] && r=ok || { r=BAD; fails=$((fails+1)); }
  printf '%-4s %-6s exit=%s len=%-3s %s\n     -> %s\n' "$r" "$want" "$code" "${#t}" "$t" "${out:0:110}"
done
created=$(ls -A "$work" | wc -l)
echo "files created in cwd: $created"; ls -A "$work"
echo "rows=${#rows[@]} bad=$fails"
cd / && rm -rf "$work"
[ "$fails" = 0 ] && [ "$created" = 0 ]
