#!/usr/bin/env bash

set -evuo pipefail

create_metadata () {
cat <<EOF > release_channel.json
{
    "image": "fiaas/fiaas-deploy-daemon:$version",
    "build": "https://fiaas.semaphoreci.com/jobs/$SEMAPHORE_JOB_ID",
    "commit": "https://github.com/fiaas/fiaas-deploy-daemon/commit/$SEMAPHORE_GIT_SHA",
    "spec": "https://fiaas.github.com/releases/artifacts/$version/fiaas.yml",
    "updated": "$(date)"
}
EOF
cat release_channel.json
}

echo "publishing release channel metadata"

if [ ! -f ./release_channel.json ]; then
    create_metadata
fi

git config --global user.email "fiaas@googlegroups.com"
git config --global user.name "Captain fiaas"
git clone https://github.com/fiaas/releases releases-repo
cd ./releases-repo
if [ -n "${1:-}" ]; then
    \cp ../release_channel.json ./fiaas-deploy-daemon/$1.json
else
    mkdir -p ./artifacts/${version}/
    cp ../fiaas.yml ./artifacts/${version}/
    git add ./artifacts/${version}
fi
git add .
git commit -a -m "Release fiaas-deploy-daemon $version"
git push https://${GITHUBKEY}@github.com/fiaas/releases

echo "Successfully published release channel metadata"
