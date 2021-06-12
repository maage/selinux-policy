#!/bin/bash

set -epux -o pipefail

make bare
mkdir -p tmp/install/var/lib/selinux/targeted
make -j"$(nproc)" -O --warn-undefined-variables DISTRO=redhat UBAC=n DIRECT_INITRC=n MONOLITHIC=n MLS_CATS=1024 MCS_CATS=1024 UNK_PERMS=allow NAME=targeted TYPE=mcs DESTDIR=tmp/install 'SEMODULE=/usr/sbin/semodule -v -p tmp/install -X 100 ' base.pp validate modules install install-appconfig load
