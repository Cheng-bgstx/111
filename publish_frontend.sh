#!/bin/bash
set -e

# ==========================================
# 配置区域（敏感信息请用环境变量，不要写死）
# ==========================================
# GITHUB_TOKEN: 必须在运行前 export，或在此脚本外设置，例如:
#   export GITHUB_TOKEN="ghp_xxxx"
# 建议使用 GitHub → Settings → Developer settings → Personal access tokens，
# 仅勾选 repo 与 workflow 最小权限。
GITHUB_USER="${GITHUB_USER:-Cheng-bgstx}"
GITHUB_REPO="${GITHUB_REPO:-111}"
FORCE_PUSH="${FORCE_PUSH:-0}"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ 错误：请设置环境变量 GITHUB_TOKEN 后再运行此脚本。"
    echo "   例: export GITHUB_TOKEN=\"ghp_xxxx\""
    exit 1
fi

DIR_FRONTEND="/limx_embap/tos/user/Jensen/dataset/motion_data/humanoid-policy-viewer-main"
CURRENT_TIME=$(date "+%Y-%m-%d %H:%M:%S")

echo ">>> [1/6] 初始化安全环境..."
cd $DIR_FRONTEND

# 1. API 地址与 API Key 不写入仓库，由 GitHub 构建时从 Secret 注入
#    请在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加:
#    - VITE_TEXT_MOTION_API_URL（必填）: 你的后端 API 地址，如 https://xxx.trycloudflare.com
#    - VITE_API_KEY（可选）: 与后端 API_KEY 一致，启用后请求会带 Authorization: Bearer
echo "✅ 构建时将使用 GitHub Secrets：VITE_TEXT_MOTION_API_URL（必填）、VITE_API_KEY（可选）"

# 2. 配置 .gitignore（确保 Token、.env 不进入仓库；.sh 脚本可提交）
echo ">>> [2/6] 配置 .gitignore..."
cat > .gitignore <<EOF
node_modules/
dist/
venv/
__pycache__/
.env
.env.*
!.env.example
deploy.env
.DS_Store
text_motion_api/venv/
*.log
.git/
EOF

# 3. 生成 GitHub Actions 工作流（使用 Secret，不写入真实 API 地址）
echo ">>> [3/6] 生成安全构建脚本..."
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml <<'WORKFLOWEOF'
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm install
      - run: npm run build
        env:
          VITE_TEXT_MOTION_API_URL: ${{ secrets.VITE_TEXT_MOTION_API_URL }}
          VITE_API_KEY: ${{ secrets.VITE_API_KEY }}
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
WORKFLOWEOF

# 4. 提交代码（无变更时做空提交以便触发 Actions 重新构建，使新 Secret 生效）
echo ">>> [4/6] 提交代码..."
if [ ! -d ".git" ]; then
    git init
fi
git add -A
if git diff --cached --quiet; then
    echo "ℹ️ 无代码变更，执行空提交以触发 Actions 重新构建（使新 VITE_* 生效）。"
    git commit --allow-empty -m "chore: trigger rebuild for env/Secret update"
else
    git commit -m "Secure deploy at $CURRENT_TIME"
fi
git branch -M main

# 5. 推送到指定仓库（仅推送到 REMOTE_URL，不依赖 origin 配置，保证目标正确）
echo ">>> [5/6] 正在推送到 GitHub..."

# 安全检查：用户名与仓库名仅允许字母数字、连字符、下划线、点，防止 URL 注入
if ! [[ "${GITHUB_USER}" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
    echo "❌ 错误：GITHUB_USER 含有非法字符，拒绝推送。"
    exit 1
fi
if ! [[ "${GITHUB_REPO}" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
    echo "❌ 错误：GITHUB_REPO 含有非法字符，拒绝推送。"
    exit 1
fi

REMOTE_URL="https://github.com/${GITHUB_USER}/${GITHUB_REPO}.git"

# 同步 origin 以便后续 git 操作一致；实际推送使用显式 URL，避免推错仓库
if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$REMOTE_URL"
else
    git remote add origin "$REMOTE_URL"
fi

# 使用 Basic + x-access-token 认证（GitHub HTTPS 推荐），并禁用凭据缓存，避免 403
AUTH_B64=$(printf "x-access-token:%s" "${GITHUB_TOKEN}" | base64 -w 0 2>/dev/null || printf "x-access-token:%s" "${GITHUB_TOKEN}" | base64 | tr -d '\n')
if [ -z "$AUTH_B64" ]; then
    echo "❌ 错误：无法生成认证信息，请检查 GITHUB_TOKEN。"
    exit 1
fi

if [ "$FORCE_PUSH" = "1" ]; then
    git -c credential.helper= \
        -c http.https://github.com/.extraheader= \
        -c http.extraHeader="Authorization: Basic ${AUTH_B64}" \
        push "$REMOTE_URL" main --force
else
    git -c credential.helper= \
        -c http.https://github.com/.extraheader= \
        -c http.extraHeader="Authorization: Basic ${AUTH_B64}" \
        push "$REMOTE_URL" main
fi

# 脚本内清除敏感变量（不影响父 shell，但减少脚本后续步骤暴露）
unset AUTH_B64

echo "=================================================="
echo "✅ 安全部署完成！"
echo "  目标仓库: ${GITHUB_USER}/${GITHUB_REPO}"
echo "  页面地址: https://${GITHUB_USER}.github.io/${GITHUB_REPO}/"
echo "=================================================="
echo "⚠️  安全建议：执行后运行 unset GITHUB_TOKEN 清除本终端中的 Token。"
echo "=================================================="