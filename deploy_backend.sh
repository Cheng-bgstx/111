#!/bin/bash
set -e

# === 路径配置 ===
DIR_BASE="/limx_embap/tos/user/Jensen/dataset/motion_data"
DIR_AI="${DIR_BASE}/StableMoFusion"
DIR_GW="${DIR_BASE}/humanoid-policy-viewer-main/text_motion_api"
PYTHON_BIN=$(which python3 || which python)

echo "=================================================="
echo ">>> 🛠️ 启动后端服务 (修正版)"
echo "=================================================="

# 1. 彻底清理旧进程 (防止端口冲突)
echo "🧹 [1/4] 清理旧进程..."
pkill -f server_robot_ws.py || true
pkill -f "uvicorn" || true
pkill -f "python main.py" || true
pkill -f cloudflared || true
# 杀掉可能卡住的 defunct 进程
killall -9 uvicorn 2>/dev/null || true

# 2. 启动 AI 模型 (端口 8000)
echo "🧠 [2/4] 启动 AI 模型..."
cd $DIR_AI
# 检查脚本是否存在
if [ ! -f "scripts/server_robot_ws.py" ]; then
    echo "❌ 错误：找不到 AI 模型启动脚本！"
    echo "请检查路径: $DIR_AI/scripts/server_robot_ws.py"
    exit 1
fi

nohup $PYTHON_BIN scripts/server_robot_ws.py \
    --opt_path ./checkpoints/robot/robot_38d_new/opt.txt \
    --which_ckpt latest \
    --port 8000 \
    --host 127.0.0.1 > /root/ai.log 2>&1 &

echo "   ...AI 模型启动中 (日志: /root/ai.log)"
sleep 5

# 3. 启动 API 网关 (端口 8080)
echo "🚪 [3/4] 启动 API 网关..."
cd $DIR_GW

# 激活虚拟环境 (如果存在)
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || true
fi

# 安全：仅允许前端页面所在域名调用 API（防止任意网站调用你的后端）
# 默认允许 GitHub Pages；若使用自定义域名，请改为你的前端域名，多个用逗号分隔
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://Cheng-bgstx.github.io}"
export ALLOWED_ORIGINS="$FRONTEND_ORIGIN"
export STRICT_ORIGIN_CHECK=1
# 若启用 API Key，请先 export API_KEY=你的密钥
export API_KEY="${API_KEY:-}"
export REQUIRE_SESSION_FOR_API=1
export SERIALIZE_REMOTE_REQUESTS=1
export MAX_REQUESTS_PER_MINUTE="${MAX_REQUESTS_PER_MINUTE:-20}"
export MAX_REQUESTS_PER_MINUTE_PER_IP="${MAX_REQUESTS_PER_MINUTE_PER_IP:-60}"

# 检查 main.py 是否存在
if [ ! -f "main.py" ]; then
    echo "❌ 严重错误：在 $DIR_GW 下找不到 main.py！"
    ls -F
    exit 1
fi

# 使用 uvicorn 启动，因为它比 python main.py 更稳定
# 如果 uvicorn 命令不存在，回退到 python main.py
if command -v uvicorn &> /dev/null; then
    nohup uvicorn main:app --host 127.0.0.1 --port 8080 --workers 1 > /root/gateway.log 2>&1 &
else
    echo "⚠️ 未找到 uvicorn 命令，尝试使用 python 启动..."
    export HOST=127.0.0.1
    export PORT=8080
    nohup $PYTHON_BIN main.py > /root/gateway.log 2>&1 &
fi

echo "   ...网关启动中 (日志: /root/gateway.log)"
sleep 5

# 检查 8080 端口是否真的活了
if ! netstat -tuln | grep ":8080 " > /dev/null; then
    echo "❌ 启动失败：端口 8080 没有被监听！"
    echo "👇 查看网关报错日志:"
    tail -n 10 /root/gateway.log
    exit 1
fi

# 4. 启动 Cloudflare 隧道
echo "🚇 [4/4] 建立隧道..."
# 显式连接到 127.0.0.1:8080
nohup cloudflared tunnel --url http://127.0.0.1:8080 > /root/tunnel.log 2>&1 &

sleep 8
echo "=================================================="
echo "✅ 后端修复完成！"
echo "👇 请复制新的 API 地址 (填入前端 .env):"
echo "--------------------------------------------------"
grep -o 'https://.*\.trycloudflare.com' /root/tunnel.log | head -n 1
echo "--------------------------------------------------"
echo "如果网页还是 502，请检查: cat /root/gateway.log"