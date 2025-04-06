#!/bin/bash

set -epux -o pipefail

sed -Ez 's/#  message="type=AVC [^ ]* [^ ]* : avc: /# AVC avc: /g;s/\n# {1,2}[a-z][^\n]*//g;' | \
sed -Ez 's/\n#   / /g;s/  "\n/\n/' | \
sed -E 's/[[:space:]]+"$//;s/ (ino|pid)=[0-9]+ / \1=<\1> /g' | \
awk '!s[$0]++'
