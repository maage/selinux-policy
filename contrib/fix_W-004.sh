#!/bin/bash

set -epux -o pipefail

fcs=($(git ls-files policy/modules|grep -v example.fc|grep '\.fc$'))

suf='bin|cfg|conf|cron|ctl|dat|devfs|d-ncipher|img|init|key|lock|log|news|persist|pid|pl|pm|py|reload|rcache2|rom|service|sh|so|socket|timer|wants|xml|zones'
git grep -Pl '^[^\s]*[a-zA-Z0-9_]\.('"$suf"')\s' "${fcs[@]}" | \
xargs -r \
sed -ri 's/^([^[:space:]]*[a-zA-Z0-9_])\.('"$suf"')([[:space:]])/\1\\.\2\3/'

git grep -Pl '^[^\s]*[a-z0-9_]\.('"$suf"')\.\*\s' "${fcs[@]}" | \
xargs -r \
sed -ri 's/^([^[:space:]]*[a-z0-9_])\.('"$suf"')(\.\*[[:space:]])/\1\\.\2\3/'

git grep -Pl '^[^\s]*python[0-9]\.[0-9]+' "${fcs[@]}" | \
xargs -r \
sed -ri 's/^([^[:space:]]*python[0-9])\.([0-9]+)/\1\\.\2/'

ddirs='fsfreeze-hook|init|limits|modules|profile|proxy|rc|remotes|rsyslog|rules|tmpfiles'
git grep -Pl '^[^\s]*('"$ddirs"')\.d[(]?/' "${fcs[@]}" | \
xargs -r \
sed -ri 's,^([^[:space:]]*)('"$ddirs"')\.(d[(]?/),\1\2\\.\3,'

dots='limits|maildir|manpath|openshift|ppprc|ssh|stickshift'
git grep -Pl '^[^\s]*/\.('"$dots"')' "${fcs[@]}" | \
xargs -r \
sed -ri 's,^([^[:space:]]*/)\.('"$dots"'),\1\\.\2,'
