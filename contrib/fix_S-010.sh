#!/bin/bash

set -epux -o pipefail

SCRIPT="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="${SCRIPT%/*}"
source "$SCRIPT_DIR"/fix.functions

declare -i OPT_getattr=0
declare -i OPT_all=0

while (( $# )); do
    case "$1" in
        --getattr) OPT_getattr=1; shift ;;
        --all) OPT_all=1; shift ;;
        --) shift; break ;;
        *) break ;;
    esac
done

find_them() {
    local rule="$1"; shift

    local r="${rule%%-*}"
    local rx=(
        '/ [(]'"$rule"'[)]$/!d;'
        's/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Suggesting permission macro: ([a-z_]+) [(]replacing ([{} a-z_]+), would add [(]none[)][)] [(]'"$rule"'[)]$/\1 \2 \3 \4/;'
    )
    if (( OPT_getattr )); then
        rx+=('s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Suggesting permission macro: ([a-z_]+) [(]replacing ([{} a-z_]+), would add [{] getattr [}][)] [(]'"$rule"'[)]$/\1 \2 \3 \4/;')
    fi
    if (( OPT_all )); then
        rx+=('s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Suggesting permission macro: ([a-z_]+) [(]replacing ([{} a-z_]+), would add [{] [^}]*[}][)] [(]'"$rule"'[)]$/\1 \2 \3 \4/;')
    fi
    rx+=('/ [(]'"$rule"'[)]$/d;')
    sed -r "${rx[*]}"
}

fix_cmd() {
    local -n ref_cmd="$1"; shift
    local lineno="$1"; shift
    local f1="$1"; shift

    [ "$1" == "{" ]
    shift
    ref_cmd+=("$lineno"'{s/\s*\b'"$(sed_escape "$1")"'\b\s*/ '"$f1"' /};')
    shift
    local f2
    for f2 in "$@"; do
        [ "$f2" != "}" ] || break
        ref_cmd+=("$lineno"'{s/\s*\b'"$(sed_escape "$f2")"'\b\s*/ /};')
    done
    ref_cmd+=("$lineno"'{s/\s*[{]\s*('"$f1"')\s*[}];\s*/ \1;/};')
}

find_and_apply_fixes S-010

# fix name order too as it migh be messed up
"$SCRIPT_DIR"/fix_C-005.sh
