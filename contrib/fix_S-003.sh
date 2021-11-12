#!/bin/bash

set -epux -o pipefail

git grep -Pl '\);' $(git ls-files policy/modules) | \
xargs -r \
sed -ri 's/^([[:space:]]*[^ ]+[(].*[)]);/\1/'
