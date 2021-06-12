#!/bin/bash

set -epux -o pipefail

make -j
mkdir -p tmp/install/var/lib/selinux/targeted
make DISTRO=redhat UBAC=n DIRECT_INITRC=n MONOLITHIC=n MLS_CATS=1024 MCS_CATS=1024 UNK_PERMS=allow NAME=targeted TYPE=mcs DESTDIR=tmp/install 'SEMODULE=/usr/sbin/semodule -v -p tmp/install -X 100 ' load
