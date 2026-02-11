# 部署与安全说明

本文档说明：1) 安全隐患与完全修正步骤；2) GitHub Actions deploy-pages 报 404 的解决办法；3) 如何确保只推送到当前仓库（如 111），不把 t2m 等内容带入。

---

## 1. 安全隐患与完全修正

### 已做对的
- 后端仅监听 127.0.0.1，通过 Cloudflare 暴露
- API 校验 Origin、会话绑定、限流
- 前端构建用 GitHub Secret 注入 API 地址，不写死
- 推送时用环境变量 GITHUB_TOKEN，不写进脚本

### 必须做的修正（建议逐项完成）

| 项 | 操作 |
|----|------|
| Token 轮换 | 若 PAT 曾明文出现在终端/脚本，立即在 GitHub → Settings → Developer settings → Personal access tokens 中 Revoke 旧 token，新建 Fine-grained token，仅选仓库 111，权限：Contents Read and write、Workflows Read and write、Metadata Read |
| 推送后清理 | 每次执行完 `publish_frontend.sh` 后执行：`unset GITHUB_TOKEN AUTH_B64` |
| 分支保护 | 仓库 111 → Settings → Branches → Add rule：main，勾选 Require a pull request、Do not allow force push（避免误强推覆盖历史） |
| Pages 来源 | 仅使用 GitHub Actions 部署，不在 Settings → Pages 里选 “Deploy from a branch”（见下文） |
| 固定域名（可选） | 生产建议用固定域名 + Cloudflare WAF/Access，替代临时 trycloudflare.com |

---

## 2. 解决 Actions 里 deploy-pages@v4 报 404（传输失败）

报错示例：
```text
Error: Failed to create deployment (status: 404)
Ensure GitHub Pages has been enabled: https://github.com/Cheng-bgstx/111/settings/pages
```

**原因**：仓库未启用 GitHub Pages，或来源未选 “GitHub Actions”。

**完全修正步骤**：

1. 打开：https://github.com/Cheng-bgstx/111/settings/pages  
2. 在 **Build and deployment** 里：
   - **Source** 选 **GitHub Actions**（不要选 “Deploy from a branch”）
3. 保存后，重新跑一次 Actions 中的 “Deploy to GitHub Pages” workflow（或重新 push 一次 main 触发）。

若仍 404，再检查：
- 仓库为 Public，或你的账号有 Pages 权限
- Settings → Actions → General：Allow all actions and reusable workflows

---

## 3. 为什么原来 t2m 的修正会被带进当前仓库？如何避免？

**原因**：当前目录的 Git 历史里可能曾包含从 t2m 克隆或合并来的提交；用 `push` 推到 111 时，会把当前分支的**整段历史**（含 t2m 相关提交）都推上去，所以 111 里会看到“别人的修正”。

**如何避免（以后不再把 t2m 带进 111）**：

1. **只用一个远程**  
   - 本仓库的 `origin` 只指向你要发的仓库，例如 111：  
     `git remote set-url origin https://github.com/Cheng-bgstx/111.git`  
   - 不要添加 t2m 为 remote，也不要对 t2m 做 `pull`/`merge`。

2. **发布脚本已限制目标仓库**  
   - `publish_frontend.sh` 会用 `GITHUB_REPO`（默认 111）设置 `origin` 并只推送到该地址。  
   - 发布前确认：`echo $GITHUB_REPO` 为 `111`，且未设置成 `t2m`。

3. **若希望 111 历史里完全不要 t2m 的提交**  
   - 只能通过“新历史”覆盖：例如在全新克隆里只保留当前需要的文件，用 `git init` + `git add` + `git commit` 生成一条新历史，再 `push --force` 到 111（会改写 111 的 main 历史，请先备份或确认可接受）。  
   - 日常开发只要坚持：**只向 111 推送、从不把 t2m 设为 remote 或拉取 t2m**，就不会再新带入 t2m 的修正。

---

## 4. 快速发布检查清单

- [ ] 已设置 `export GITHUB_REPO=111`（或脚本默认 111）
- [ ] 未添加 t2m 为 remote，且未从 t2m pull
- [ ] 仓库 111 的 Pages 来源已选 **GitHub Actions**
- [ ] Secret `VITE_TEXT_MOTION_API_URL` 已在 111 中配置
- [ ] 发布后执行 `unset GITHUB_TOKEN AUTH_B64`
