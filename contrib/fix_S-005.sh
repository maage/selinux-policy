#!/bin/bash

set -epux -o pipefail

selint --source --only-enabled --enable=S-005 --enable=S-004 --recursive policy
printf "Change interface to template\n"
