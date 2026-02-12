#!/bin/bash
# Push only website-necessary files to the specified GitHub repo and deploy via Actions.
# Usage: TARGET_REPO_URL=https://github.com/OWNER/REPO.git ./push_to_github.sh
# Or:    REMOTE=origin BRANCH=main ./push_to_github.sh  (uses existing remote)

set -e
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"

cd "$REPO_ROOT"
if [ -n "$TARGET_REPO_URL" ]; then
  if git remote get-url "$REMOTE" &>/dev/null; then
    git remote set-url "$REMOTE" "$TARGET_REPO_URL"
  else
    git remote add "$REMOTE" "$TARGET_REPO_URL"
  fi
fi
git rm --cached deploy_backend.sh run_deploy_backend.sh run_deploy_frontend.sh publish_frontend.sh 2>/dev/null || true
git rm --cached deploy.env.example 2>/dev/null || true
git rm -r --cached sim2real/ 2>/dev/null || true
git add .
git status
git commit -m "Update: demo and README" || true
git push -u "$REMOTE" "$BRANCH"
