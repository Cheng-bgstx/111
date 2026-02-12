# 部署前清单

按顺序完成以下项后即可部署前后端。

---

## 一、后端部署（`deploy_backend.sh`）

### 1. 环境与路径

- [ ] **路径**：脚本内 `DIR_BASE`、`DIR_AI`、`DIR_GW` 与当前机器一致（默认 `DIR_BASE=/limx_embap/tos/user/Jensen/dataset/motion_data`）。若不同，请修改脚本或通过调用前 `cd` 到对应目录后改脚本中的路径。
- [ ] **Python**：已安装 Python 3，且 `text_motion_api` 依赖已装（建议 `cd text_motion_api && pip install -r requirements.txt`）。
- [ ] **uvicorn**：已安装（或脚本会回退到 `python main.py`）。
- [ ] **AI 模型**：`StableMoFusion` 已就绪，且存在 `scripts/server_robot_ws.py` 及对应 checkpoint（如 `checkpoints/robot/robot_38d_new/`）。
- [ ] **cloudflared**：已安装并可用（用于生成公网 URL）；启动后从 `/root/tunnel.log` 取 `https://xxx.trycloudflare.com` 作为后端 API 地址。

### 2. 安全相关（必配其一或都配）

- [ ] **ALLOWED_ORIGINS**：与前端实际访问域名一致。  
  - 脚本通过 `FRONTEND_ORIGIN` 设置，默认 `https://Cheng-bgstx.github.io`。  
  - 若前端是 GitHub Pages，改为你的 Pages 地址，例如：  
    `export FRONTEND_ORIGIN="https://你的用户名.github.io/你的仓库名/"` 再执行脚本。  
  - 若前端是 Vercel，则：  
    `export FRONTEND_ORIGIN="https://你的项目.vercel.app"`。
- [ ] **API Key（可选但推荐）**：若启用，先设置再执行脚本：  
  `export API_KEY="你的密钥"`  
  密钥需与前端构建时使用的 `VITE_API_KEY` 一致。

### 3. 执行

```bash
cd /path/to/humanoid-policy-viewer-main
export FRONTEND_ORIGIN="https://你的前端域名"   # 必配
export API_KEY="你的密钥"                      # 若启用 API Key
./deploy_backend.sh
```

执行后把终端里打印的 `https://xxx.trycloudflare.com` 记下来，用于前端配置。

---

## 二、前端部署（`publish_frontend.sh`，推送到 GitHub 并走 Actions）

### 1. GitHub 仓库与 Token

- [ ] 已有目标仓库（如 `你的用户名/你的仓库名`）。
- [ ] 已创建 **Personal access token**（Settings → Developer settings → Personal access tokens），至少勾选 `repo`。
- [ ] 运行脚本前：`export GITHUB_TOKEN="ghp_xxxx"`。  
  可选：`export GITHUB_USER=你的用户名`、`export GITHUB_REPO=仓库名`（默认见脚本内）。

### 2. GitHub Secrets（仓库 Settings → Secrets and variables → Actions）

- [ ] **VITE_TEXT_MOTION_API_URL**（必填）：后端公网地址，即 `deploy_backend.sh` 输出或 cloudflared 给出的地址，例如：  
  `https://xxx.trycloudflare.com`  
  不要末尾加 `/`。
- [ ] **VITE_API_KEY**（可选）：若后端启用了 API Key，此处填与后端 `API_KEY` 相同的值；未启用则可不建该 Secret。

### 3. 执行

```bash
cd /path/to/humanoid-policy-viewer-main
export GITHUB_TOKEN="ghp_xxxx"
export GITHUB_USER=你的用户名    # 若与默认不同
export GITHUB_REPO=仓库名        # 若与默认不同
./publish_frontend.sh
```

推送成功后，在仓库 **Actions** 中等待 workflow 完成，然后打开 **GitHub Pages** 的页面地址（如 `https://你的用户名.github.io/你的仓库名/`）。

---

## 三、前端显示 “Not Connected” 的排查

**原因**：前端创建会话（请求 `/api/session`）失败，常见如下。

### 1. 只改了 Secret、没有重新构建/部署（最常见）

- **Vite 在构建时** 才会把 `VITE_TEXT_MOTION_API_URL` 和 `VITE_API_KEY` 写进前端代码；**只改 GitHub Secrets 不会改变已部署的页面**。
- **正确做法**：在 GitHub 里更新 `VITE_TEXT_MOTION_API_URL`（以及如启用 API Key 则更新 `VITE_API_KEY`）后，**必须再触发一次前端构建与部署**，新配置才会生效。
- **操作**：重新执行一次前端部署（会推送并触发 Actions 构建）：
  ```bash
  cd /limx_embap/tos/user/Jensen/dataset/motion_data/humanoid-policy-viewer-main
  # 确保 deploy.env 里有 GITHUB_TOKEN（以及 GITHUB_USER、GITHUB_REPO 若需）
  ./run_deploy_frontend.sh
  ```
  或在 GitHub 仓库 **Actions** 页对 “Deploy to GitHub Pages” 工作流点击 **Run workflow**，跑完后刷新前端页面再试。

### 2. API Key 不一致

- 若后端在 `deploy.env` 或环境里设置了 `API_KEY`，则 GitHub Secret **VITE_API_KEY** 必须与之一字不差（同一密钥）。
- 若后端未设 API Key，则不要在前端构建里传 `VITE_API_KEY`（或删掉该 Secret），否则可能误带空/错误头。

### 3. 后端新 URL 未生效或不可达

- 在浏览器新开标签访问：`https://你的新隧道地址.trycloudflare.com/`  
  应返回 `{"status":"running"}`。若打不开或非此响应，说明隧道/后端未就绪，需先看后端日志（如 `/root/gateway.log`、`/root/tunnel.log`）。
- 新 URL 不要带末尾斜杠，例如用 `https://xxx.trycloudflare.com`，不要 `https://xxx.trycloudflare.com/`（根路径可以带 `/`，但 Secret 里填的 **VITE_TEXT_MOTION_API_URL** 建议不带末尾斜杠）。

### 4. 看浏览器具体报错

- 打开前端页面 → F12 → **Network**，刷新或点击 “Generate motions with AI”，找到对 `session` 或 `api/session` 的请求：
  - **CORS 报错**：检查后端 `FRONTEND_ORIGIN` / `ALLOWED_ORIGINS` 是否包含你前端访问的 Origin（如 `https://cheng-bgstx.github.io`）。
  - **401**：API Key 校验失败，检查前后端密钥是否一致、是否重新部署了前端。
  - **404 /  Failed to fetch**：请求的 base URL 仍是旧的或写错，说明前端未用新 URL 构建，按第 1 步重新部署。

---

## 四、部署后核对

- [ ] 浏览器打开前端页面，能正常加载。
- [ ] 若启用了 API Key：未配置或配错会 401；前后端密钥一致且 CORS 为前端域名时应正常。
- [ ] 若出现 CORS 或 403：检查后端 `ALLOWED_ORIGINS`（或 `FRONTEND_ORIGIN`）是否与前端访问的 **Origin** 完全一致（协议 + 域名 + 端口）。
- [ ] 文本生成动作：确认后端能连上 AI 模型（端口 8000）且 cloudflared 隧道正常；异常可查 `/root/gateway.log`、`/root/ai.log`、`/root/tunnel.log`。

---

## 五、小结

| 项目           | 后端                         | 前端（GitHub）                          |
|----------------|------------------------------|-----------------------------------------|
| 必配           | `FRONTEND_ORIGIN`（或脚本内 ALLOWED_ORIGINS） | Secret: `VITE_TEXT_MOTION_API_URL`      |
| 推荐           | `API_KEY`                    | Secret: `VITE_API_KEY`（与后端一致）    |
| 路径/环境      | `DIR_*`、Python、uvicorn、AI、cloudflared | `GITHUB_TOKEN`、仓库与 Pages 已开启     |

完成以上即可部署；若使用 Vercel 等其它前端托管，只需把 `FRONTEND_ORIGIN` 设为该站点域名，并在对应平台配置 `VITE_TEXT_MOTION_API_URL` 与（可选）`VITE_API_KEY` 即可。
