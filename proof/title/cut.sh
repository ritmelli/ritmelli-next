# usage: cut.sh <step name>  (reads budget.yml on stdin, prints the dedented run: block)
awk -v want="$1" '
  /^      - name: / { inside = ($0 == "      - name: " want); inrun = 0; next }
  inside && /^        run: \|$/ { inrun = 1; next }
  inside && inrun { if ($0 ~ /^          / || $0 == "") { sub(/^          /, ""); print } else { inrun = 0 } }
'
