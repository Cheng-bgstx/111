#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -f deploy.env ]; then
  set -a
  source deploy.env
  set +a
fi
export FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://cheng-bgstx.github.io}"
export API_KEY="${API_KEY:-}"
./deploy_backend.sh
