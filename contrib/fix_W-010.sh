#!/bin/bash

set -epux -o pipefail

git grep -lP '\b(domain_trans|domain_auto_trans)[(]'|\
xargs -r \
sed -ri '
s/\bdomain_trans[(]/domain_transition_pattern(/;
s/\bdomain_auto_trans[(]/domain_auto_transition_pattern(/;
'
selint --source --only-enabled --enable=W-010 --recursive policy
