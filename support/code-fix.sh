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
    A002
    ARG002
    B006
    B007
    COM819
    D206
    D210
    D213
    D300
    D406
    D407
    E101
    E401
    E701
    E703
    E711
    E712
    E713
    E721
    EM101
    EM102
    EXE001
    F841
    I001
    ISC003
    N806
    N818
    PERF102
    PIE808
    PLR1714
    PLR1722
    PLR5501
    Q000
    Q002
    Q003
    RET503
    RET504
    RET505
    RET507
    SIM102
    SIM108
    SIM109
    SIM114
    SIM115
    SIM118
    SIM201
    UP010
    UP015
    UP032
    UP036
    UP039
    TRY003
    UP031
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
    consider-using-in
    consider-using-with
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
