#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -f deploy.env ]; then
  set -a
  source deploy.env
  set +a
fi
export GITHUB_USER="${GITHUB_USER:-Cheng-bgstx}"
export GITHUB_REPO="${GITHUB_REPO:-111}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
./publish_frontend.sh
