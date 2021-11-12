#!/bin/bash

set -epux -o pipefail

selint --source --only-enabled --enable=W-006 --recursive policy | \
grep -Ev '_stub_|_stub |corenet_enable_unlabeled_packets'
