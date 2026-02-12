# 安全与配置说明

本文档汇总当前项目的**已知问题**与**安全相关配置**，便于部署与审计。

---

## 一、已修复/已加固项

### 1. 错误信息泄露（已修复）

- **问题**：生成动作失败时，API 将内部异常 `str(e)` 直接返回给客户端，可能泄露路径、依赖等内部信息。
- **处理**：`text_motion_api/main.py` 中 500 响应仅返回通用文案 `"Failed to generate motion"`，详细错误仅写服务端日志。

### 2. Session ID 校验（已加固）

- **问题**：`X-Session-ID` 未做格式校验，异常或超长头可能带来隐患。
- **处理**：仅接受 **UUID 格式** 的 session_id，否则返回 400 `INVALID_SESSION_ID`。

### 3. CORS 与 ALLOWED_ORIGINS

- **问题**：`allow_credentials=True` 时使用 `allow_origins=["*"]` 会被浏览器拒绝；未配置 `ALLOWED_ORIGINS` 且开启严格检查时可能返回 500。
- **处理**：
  - 当配置为 `ALLOWED_ORIGINS=*` 时，代码中不再使用 `*` 作为 origin 列表（避免与 credentials 冲突）。
  - `.env.example` 中改为示例具体域名，并说明生产环境应配置为显式 origin 列表。
  - 本地开发可设置 `STRICT_ORIGIN_CHECK=0` 关闭 origin 检查（仅建议在可信环境使用）。

---

## 二、安全相关配置（需按环境调整）

### 1. 会话与“客户端”绑定

- **ALLOW_SESSION_REBIND**（默认 `1`）
  - `1`：同一 session_id 可在不同 IP/设备上使用，服务端会更新会话的 client_fingerprint（便于多设备/换网络后继续用）。
  - `0`：仅允许创建会话时的 IP/User-Agent 使用该会话，否则返回 403 `SESSION_FORBIDDEN`。
  - **建议**：内网或演示环境可用 `1`；对安全要求高、需严格绑定设备时设为 `0`。

### 2. 客户端指纹

- 会话绑定依据为 **client_fingerprint** = `SHA256(client_ip + "|" + User-Agent)`。
- **TRUST_PROXY_HEADERS**（默认 `0`）
  - `1` 时使用 `X-Forwarded-For` 第一个 IP 作为 client_ip。仅在**前置为可信反向代理**时设为 `1`，否则可能被伪造 IP。

### 3. Origin 检查

- **STRICT_ORIGIN_CHECK**（默认 `1`）
  - `1`：每个 API 请求都会校验 `Origin` 是否在 `ALLOWED_ORIGINS` 中。
  - `0`：不校验 Origin（仅建议本地/内网开发用）。
- **ALLOWED_ORIGINS**：逗号分隔的合法前端来源，例如  
  `http://localhost:5173,https://yourdomain.com`。**不要**在生产环境使用 `*`（且与 credentials 不兼容）。

### 4. 前端 API 地址

- 前端默认请求 `VITE_TEXT_MOTION_API_URL` 或 `http://localhost:8080`。
- 生产部署时请通过构建环境变量指定为实际 API 地址，避免暴露或误用本地地址。

---

## 三、当前限制与已知风险

### 1. 无用户认证

- 接口**无登录/鉴权**，仅依赖会话 ID + 客户端指纹绑定会话。
- 会话 ID 为 UUID，不可预测，但一旦泄露（如被截获、共享），他人可在满足 CORS 的前提下以该会话访问对应数据。
- **建议**：对敏感或生产环境，在前置网关或本服务前增加认证（如 OAuth、JWT、API Key）。

### 2. 会话劫持（ALLOW_SESSION_REBIND=1 时）

- 开启“会话重新绑定”时，任何人拿到 session_id（如从另一设备复制）都可在自己浏览器中“接管”该会话。
- **建议**：若需严格“一会话一设备”，设置 `ALLOW_SESSION_REBIND=0`。

### 3. 上传与输入

- **前端**：本地上传的 JSON 动作文件仅在浏览器内解析并用于仿真，**未上传到本 API 服务**，不增加服务端文件上传风险。
- **API**：生成接口的 `text`、数值参数等由 Pydantic 做长度与范围校验；`motion_id` 由服务端生成并仅作 session 内 key，无路径遍历。

### 4. 依赖与构建

- 未在本文档中执行依赖漏洞扫描；建议定期执行 `npm audit` / `pip audit` 等并根据结果升级依赖。
- 生产构建请使用 `npm run build` 等正式流程，并确保未带入开发环境中的敏感占位符。

---

## 四、配置检查清单（部署前）

- [ ] 生产环境已设置 `ALLOWED_ORIGINS` 为具体前端域名（不用 `*`）。
- [ ] 若使用反向代理，确认是否需要并正确设置 `TRUST_PROXY_HEADERS`。
- [ ] 按安全策略决定是否设置 `ALLOW_SESSION_REBIND=0`。
- [ ] 前端构建已配置正确的 `VITE_TEXT_MOTION_API_URL`（或等价方式）。
- [ ] 敏感配置仅通过环境变量或密钥管理注入，未写入代码或提交到仓库。
