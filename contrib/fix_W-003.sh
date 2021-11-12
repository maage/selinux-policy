#!/bin/bash

set -epux -o pipefail

SCRIPT="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="${SCRIPT%/*}"
source "$SCRIPT_DIR"/fix.functions

rule=W-003

find_them() {
    local rule="$1"; shift

    local r="${rule%%-*}"
    sed -r '
/ [(]'"$rule"'[)]$/!d;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Attribute ([^ ]+) is listed in require block but not used in interface [(]'"$rule"'[)]$/\1 \2 attribute \3/;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Role ([^ ]+) is listed in require block but not used in interface [(]'"$rule"'[)]$/\1 \2 role \3/;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Role Attribute ([^ ]+) is listed in require block but not used in interface [(]'"$rule"'[)]$/\1 \2 attribute_role \3/;
s/^([^:]+):[[:space:]]*([0-9]+): [(]'"$r"'[)]: Type ([^ ]+) is listed in require block but not used in interface [(]'"$rule"'[)]$/\1 \2 type \3/;
/ [(]'"$rule"'[)]$/d;
'
}

rule_filenames=()
get_rule_filenames rule_filenames "$rule"
for fname in "${rule_filenames[@]}"; do
    filenames=()
    get_filenames filenames "$fname"
    for filename in "${filenames[@]}"; do
        while true; do
            cmd=()
            while read -r _ lineno n f1; do
                # Remove element
                # If empty, skip (delete)
                # Fix starting comma
                # Fix middle/end comma / ;
                # shellcheck disable=SC2016
                cmd+=(
                    'if ($lineno == '"$lineno"') {
                        s/^(\s*\Q'"$n"'\E\b.*)\b\Q'"$f1"'\E\b\s*(.*)/$1 $2/;
                        if (/^\s*\Q'"$n"'\E\s*;/){next};
                        s/(\b\Q'"$n"'\E)\s+,\s*/$1 /;
                        s/,\s*([,;])/$1/g;
                    };'
                )
            done < <(selint_base "$rule" --context=policy "$filename" | find_them "$rule")
            wait $!

            (( ${#cmd[@]} )) || break

            # Complex because we
            # - skip stubs: at=1
            # - can remove one of types in line
            # - can remove all of types in line
            # - can remove all types in require
            #   - at=2 gen_require until it ends
            #   - at=3 empty lines after gen_require we want to delete too
            perl -e '
            my $at = 0;
            my @lines;
            my $lineno = 0;
            while (<>) {
                $lineno ++;
                if ($at == 0 and /^(?:interface|template)/) {
                    if (/stub/) {
                        $at = 1;
                    }
                }
                if ($at == 1) {
                    if (/^'"'"'[)]\s*$/) {
                        $at = 0;
                    }
                    print;
                    next;
                }
                '"${cmd[*]}"'
                if ($at == 0 and /^\s*gen_require[(][`]\s*$/) {
                    $at = 2;
                    push @lines, $_;
                    next;
                }
                if ($at == 2 and /^\s*'"'"'[)]\s*$/) {
                    $at = 3;
                    @lines = ();
                    next;
                }
                next if ($at >= 2 and /^\s*$/);
                $at = 0;
                for my $l (@lines) {
                    print $l
                }
                @lines = ();
                print;
            }' "$filename" > "$filename".tmp
            if cmp -s "$filename".tmp "$filename"; then
                rm "$filename".tmp
                break
            fi
            mv -- "$filename".tmp "$filename"
        done
    done
done
