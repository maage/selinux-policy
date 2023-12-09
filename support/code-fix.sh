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

if false; then
! pyflakes "${py_files[@]}" |& grep ^ || exit 1
fi

if false; then
pyupgrade --py311-plus "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1
fi

if false; then
black --target-version py311 "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1
fi



ruf=(
    D206
    E101
    SIM118
    W191
)
if (( ${#ruf[@]} )); then
ruf2="${ruf[*]}"
ruff check --select="${ruf2// /,}" "${py_files[@]}"
fi



pyl=(
    consider-iterating-dictionary
    consider-using-dict-items
    undefined-variable
)
if (( ${#pyl[@]} )); then
pyl2="${pyl[*]}"
pylint --disable=all --enable="${pyl2// /,}" "${py_files[@]}"
fi
