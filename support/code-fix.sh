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

black --target-version py311 "${py_files[@]}"
! git status --porcelain | grep -Ev '^[?][?] ' || exit 1



ruf=(
    COM819
    D206
    D210
    D213
    D300
    E101
    E401
    E701
    E703
    E711
    E713
    E721
    F841
    I001
    ISC003
    Q000
    Q002
    Q003
    RET505
    RET507
    SIM102
    SIM108
    SIM114
    SIM118
    SIM201
    UP010
    UP015
    UP032
    UP036
    UP039
    W191
)
if (( ${#ruf[@]} )); then
ruf2="${ruf[*]}"
ruff check --select="${ruf2// /,}" "${py_files[@]}"
fi



pyl=(
    anomalous-backslash-in-string
    bad-indentation
    colon
    consider-iterating-dictionary
    consider-using-dict-items
    line-too-long
    multiple-statements
    no-else-continue
    no-else-return
    simplifiable-if-statement
    syntax-error
    trailing-newlines
    undefined-variable
    unidiomatic-typecheck
    unnecessary-semicolon
    unused-import
    use-implicit-booleaness-not-len
)
if (( ${#pyl[@]} )); then
pyl2="${pyl[*]}"
pylint --disable=all --enable="${pyl2// /,}" "${py_files[@]}"
fi
