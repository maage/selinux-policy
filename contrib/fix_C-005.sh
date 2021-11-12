#!/bin/bash

set -epux -o pipefail

SCRIPT="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="${SCRIPT%/*}"
source "$SCRIPT_DIR"/fix.functions

find_them() {
    local rule="$1"; shift

    local r="${rule%%-*}"
    sed -r '
/ [(]'"$rule"'[)]$/!d;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Permissions in av rule not ordered [(]([^ ]+) before ([^)]+)[)] [(]'"$rule"'[)]/\1 \2 \3 \4/;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Permissions in class declaration not ordered [(]([^ ]+) before ([^)]+)[)] [(]'"$rule"'[)]/\1 \2 \3 \4/;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Permissions in av rule repeated [(]([^ ]+)[)] [(]'"$rule"'[)]/\1 \2 \3 \3/;
/ [(]'"$rule"'[)]$/d;
'
}

fix_cmd() {
    local -n ref_cmd="$1"; shift
    local lineno="$1"; shift
    local f1="$1"; shift
    local f2="$1"; shift

    if [ "$f1" == "$f2" ]; then
        ref_cmd+=("$lineno"'{s/^(.*[^[:space:]])[[:space:]]*'"$f1"'[[:space:]]+'"$f2"'[[:space:]]*(.*)/\1 '"$f1"' \2/};')
    else
        ref_cmd+=("$lineno"'{s/^(.*[^[:space:]])[[:space:]]*'"$f1"'[[:space:]]+'"$f2"'[[:space:]]*(.*)/\1 '"$f2 $f1"' \2/};')
    fi
}

find_and_apply_fixes C-005
