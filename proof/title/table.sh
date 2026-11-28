# usage: bash table.sh <title of main.sh> <title of the head.sh>
# each row: expect|title (expect = pass, format, period, length), the 42 rows of #96 and three more.
# The head must give the expected result on every row. Main must give the same exit code and
# output as the head on every row but the Revert button row, where it gives the format error.
main=$1 head=$2
work=$(mktemp -d); cd "$work" || exit 9
p100="feat(installer): $(printf 'a%.0s' $(seq 1 83))"
p101="feat(installer): $(printf 'a%.0s' $(seq 1 84))"
button='Revert "feat(machine): port the --microfone mode"'
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
  "pass|$button"
  "format|Revert"
  'format|revert "x"'
)
expected() {
  case $1 in
    pass) [ "$2" = 0 ] && [ -z "$3" ];;
    format) [ "$2" = 1 ] && [[ $3 == "::error::the PR title must be '<type>(<scope>): <description>'"* ]];;
    period) [ "$2" = 1 ] && [ "$3" = "::error::the PR title must not end with a period: drop it" ];;
    length) [ "$2" = 1 ] && [ "$3" = "::error::shorten the PR title (${#4} characters, the limit is 100)" ];;
  esac
}
fails=0 n=0
for row in "${rows[@]}"; do
  n=$((n+1)); want=${row%%|*}; t=${row#*|}
  hout=$(TITLE="$t" bash --noprofile --norc -eo pipefail "$head" 2>&1); hcode=$?
  mout=$(TITLE="$t" bash --noprofile --norc -eo pipefail "$main" 2>&1); mcode=$?
  ok=y
  expected "$want" "$hcode" "$hout" "$t" || ok=n
  if [ "$t" = "$button" ]; then
    expected format "$mcode" "$mout" "$t" || ok=n
    same="main format error"
  elif [ "$mcode" = "$hcode" ] && [ "$mout" = "$hout" ]; then
    same="same on main"
  else
    same="DIFFERS on main"; ok=n
  fi
  [ $ok = y ] && r=ok || { r=BAD; fails=$((fails+1)); }
  printf '%2s %-4s %-6s head=%s main=%s %-17s len=%-3s %s\n     -> %s\n' "$n" "$r" "$want" "$hcode" "$mcode" "$same" "${#t}" "$t" "${hout:0:100}"
done
created=$(ls -A "$work" | wc -l)
echo "files created in cwd: $created"; ls -A "$work"
echo "rows=${#rows[@]} bad=$fails"
cd / && rm -rf "$work"
[ "$fails" = 0 ] && [ "$created" = 0 ] && [ "${#rows[@]}" = 45 ]
