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
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: No mls levels specified in gen_context [(]'"$rule"'[)]$/\1 \2/;
/ [(]'"$rule"'[)]$/d;
'
}

fix_cmd() {
    local -n ref_cmd="$1"; shift
    local lineno="$1"; shift

    ref_cmd+=("$lineno"'{s/[)]/,s0)/};')
}

find_and_apply_fixes S-007
