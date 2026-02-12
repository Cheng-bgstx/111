#!/bin/bash
case "$1" in
    logs)
        echo "正在查看日志 (Ctrl+C 退出)..."
        tail -f /var/log/ai.log /var/log/gateway.log
        ;;
    restart)
        echo "正在重启后台服务..."
        bash /root/deploy_backend.sh
        ;;
    check)
        echo "端口占用情况："
        netstat -tulnp | grep -E '80|8000|8080'
        ;;
    *)
        echo "用法: bash manage.sh {logs|restart|check}"
        ;;
esac