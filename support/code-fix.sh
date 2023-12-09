#!/bin/bash

set -epux

py_files=(support/*.py policy/flask/flask.py)

if false; then
sed -Ei 's/[[:blank:]]+$//' "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1
fi

sed -Ei '
    s/^(\s*)\t/\1    /g;
    s/^(\s*)\t/\1    /g;
    s/^(\s*)\t/\1    /g;
    s/^(\s*)\t/\1    /g;
    s/^(\s*)\t/\1    /g;
    s/^(\s*)\t/\1    /g;
    s/^(\s*)\t/\1    /g
' "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1

! pyflakes "${py_files[@]}" |& grep 'invalid syntax' || exit 1

! pyflakes "${py_files[@]}" |& grep ^ || exit 1

pyupgrade --py311-plus "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1

if false; then
black --target-version py311 "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1
fi



ruf=(
    D206
    E101
    F841
    SIM118
    UP010
    UP015
    UP032
    UP036
    W191
)
if (( ${#ruf[@]} )); then
ruf2="${ruf[*]}"
ruff check --select="${ruf2// /,}" "${py_files[@]}"
fi



pyl=(
    anomalous-backslash-in-string
    consider-iterating-dictionary
    consider-using-dict-items
    syntax-error
    undefined-variable
    unused-import
)
if (( ${#pyl[@]} )); then
pyl2="${pyl[*]}"
pylint --disable=all --enable="${pyl2// /,}" "${py_files[@]}"
fi
