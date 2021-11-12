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
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Recommend use of self keyword instead of redundant type [(]'"$rule"'[)]$/\1 \2/;
/ [(]'"$rule"'[)]$/d;
'
}

fix_cmd() {
    local -n ref_cmd="$1"; shift
    local lineno="$1"; shift

    ref_cmd+=("$lineno"'{s/(allow|dontaudit)[[:space:]]+([^ ]+_t)[[:space:]]+\2[[:space:]]*:[[:space:]]*/\1 \2 self:/};')
}

find_and_apply_fixes C-007
