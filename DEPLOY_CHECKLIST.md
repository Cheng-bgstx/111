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

## 三、部署后核对

- [ ] 浏览器打开前端页面，能正常加载。
- [ ] 若启用了 API Key：未配置或配错会 401；前后端密钥一致且 CORS 为前端域名时应正常。
- [ ] 若出现 CORS 或 403：检查后端 `ALLOWED_ORIGINS`（或 `FRONTEND_ORIGIN`）是否与前端访问的 **Origin** 完全一致（协议 + 域名 + 端口）。
- [ ] 文本生成动作：确认后端能连上 AI 模型（端口 8000）且 cloudflared 隧道正常；异常可查 `/root/gateway.log`、`/root/ai.log`、`/root/tunnel.log`。

---

## 四、小结

| 项目           | 后端                         | 前端（GitHub）                          |
|----------------|------------------------------|-----------------------------------------|
| 必配           | `FRONTEND_ORIGIN`（或脚本内 ALLOWED_ORIGINS） | Secret: `VITE_TEXT_MOTION_API_URL`      |
| 推荐           | `API_KEY`                    | Secret: `VITE_API_KEY`（与后端一致）    |
| 路径/环境      | `DIR_*`、Python、uvicorn、AI、cloudflared | `GITHUB_TOKEN`、仓库与 Pages 已开启     |

完成以上即可部署；若使用 Vercel 等其它前端托管，只需把 `FRONTEND_ORIGIN` 设为该站点域名，并在对应平台配置 `VITE_TEXT_MOTION_API_URL` 与（可选）`VITE_API_KEY` 即可。
