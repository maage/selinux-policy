#!/bin/bash

set -epux -o pipefail

disables=(
    # Checked below
    C-004 # Interface does not have documentation comment

    # This is handled by 'make validate'
    W-001 # Type or attribute referenced without explicit declaration

    # Leftover are stubs, checked below
    W-003 # Unused type, attribute or role listed in require block

    # This is handled by 'make validate'
    W-005 # Interface call from module not in optional_policy block

    # Leftover are stubs, checked below
    W-006 # Interface call with empty argument

    # Not going to fix these for now
    W-008 # Allow rule with complement or wildcard permission

    # Some kind of interface issue, not going to fix
    W-011 # Declaration in require block not defined in own module

    S-001 # Require block used instead of interface call
    S-002 # File context file labels with type not declared in module

    # Have not fixed all of these as suggestions add perms
    S-010 # Permission macro usage suggested
)

args=()
for d in "${disables[@]}"; do
    args+=(--disable="$d")
done
selint "${args[@]}" --source --recursive policy

# these interfaces are just copies of respective containers
selint --source --only-enabled --enable=C-004 --recursive policy | sed '/^container\.if: .* for docker_/d'

# Entries left are in stubs
contrib/fix_W-003.sh
rc=0
git status --porcelain | grep -Eq '^' || rc=$?
if [ $rc -eq 0 ]; then
    git diff
    exit 1
fi

contrib/fix_W-006.sh
