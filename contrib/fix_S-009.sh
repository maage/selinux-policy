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
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Permission macro ([a-z_]+) does not match class ([a-z_]+) [(]'"$rule"'[)]/\1 \2 \3 \4/;
/ [(]'"$rule"'[)]$/d;
'
}

fix_cmd() {
    local -n ref_cmd="$1"; shift
    local lineno="$1"; shift
    local macro="$1"; shift
    local class="$1"; shift

    local repl=
    case "$macro" in
        *_blk_file_perms)
            case "$class" in
                chr_file) repl="${macro%_blk_file_perms}_${class}_perms" ;;
            esac ;;
        *_chr_file_perms)
            case "$class" in
                blk_file) repl="${macro%_chr_file_perms}_${class}_perms" ;;
            esac ;;
    esac
    if [ ! "$repl" ]; then
        case "$class" in
            blk_file|chr_file|fifo_file|lnk_file|sock_file)
                case "$macro" in
                    create_file_perms|delete_file_perms|manage_file_perms|read_inherited_file_perms|read_file_perms|relabel_file_perms|rw_inherited_file_perms|rw_file_perms|write_file_perms) repl="${macro%_file_perms}_${class}_perms" ;;
                    *) ;;
                esac ;;
            dir)
                case "$macro" in
                    read_file_perms) repl=list_dir_perms ;;
                    *_file_perms) repl="${macro%_file_perms}_dir_perms" ;;
                    *) ;;
                esac ;;
            file)
                case "$macro" in
                    *_lnk_file_perms) repl="${macro%_lnk_file_perms}_file_perms" ;;
                    *) ;;
                esac ;;
            filesystem)
                case "$macro" in
                    relabel_file_perms) repl="{ relabelfrom relabelto }" ;;
                    mount_fs_perms) repl=mount_filesystem_perms ;;
                    *) ;;
                esac ;;
            shm)
                case "$macro" in
                    *_sem_perms) repl="${macro%_sem_perms}_shm_perms" ;;
                    *) ;;
                esac ;;
            unix_stream_socket)
                case "$macro" in
                    relabel_file_perms) repl="{ getattr relabelfrom relabelto }" ;;
                    *) ;;
                esac ;;
            *) ;;
        esac
    fi
    [ "$repl" ] || return 0

    ref_cmd+=("$lineno"'{s/:\s*\b('"$(sed_escape "$class")"')\b\s+\b'"$(sed_escape "$macro")"'\b\s*;\s*$/:\1 '"$repl"';/};')
    ref_cmd+=("$lineno"'{s/:\s*\b('"$(sed_escape "$class")"')\b\s*([{].*)\b'"$(sed_escape "$macro")"'\b\s*(.*[}])\s*;\s*$/:\1 \2'"$repl"' \3;/};')
}

find_and_apply_fixes S-009
selint --source --only-enabled --enable=S-009 --recursive policy
