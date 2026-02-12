# Push to GitHub (website-only; keep this file local)

## What gets pushed

- Everything **not** listed in `.gitignore`: `src/`, `public/`, `index.html`, `package.json`, `package-lock.json`, `vite.config.mjs`, `jsconfig.json`, `.nojekyll`, `.github/`, `README.md`, `.gitignore`, `.browserslistrc`, `.editorconfig`, and `text_motion_api/` (backend code, no secrets).

## What is not pushed (ignored)

- `deploy_backend.sh`, `run_deploy_backend.sh`, `run_deploy_frontend.sh`, `publish_frontend.sh`, `deploy.env`, `deploy.env.example`, `text_motion_api/venv/`, `text_motion_api/.env`, `PUSH_COMMANDS.md`.

## Commands (run from repo root)

```bash
cd /limx_embap/tos/user/Jensen/dataset/motion_data/humanoid-policy-viewer-main

# Optional: stop tracking deployment files if they were committed before
git rm --cached deploy_backend.sh run_deploy_backend.sh run_deploy_frontend.sh publish_frontend.sh 2>/dev/null || true
git rm --cached deploy.env.example 2>/dev/null || true

git add .
git status
git commit -m "Update demo and README"
git push origin main
```

Replace `origin` with your remote name and `main` with your branch if different.
