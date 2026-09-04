#!/bin/bash
set -e

echo "===== 部署 E_listening 英语精听训练工具 ====="

# 1. 安装系统依赖
echo "[1/6] 安装系统依赖..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ffmpeg

# 2. 克隆项目
echo "[2/6] 克隆项目..."
cd /opt
if [ -d "E_listening" ]; then
    echo "目录已存在，拉取最新代码..."
    cd E_listening
    git pull
else
    git clone https://github.com/lanhuahuang470-ai/E_listening.git
    cd E_listening
fi

# 3. 创建虚拟环境并安装依赖
echo "[3/6] 安装 Python 依赖..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. 配置 .env
echo "[4/6] 配置 .env..."
read -p "请输入你的 DeepSeek API Key (直接回车跳过，翻译功能不可用): " API_KEY
if [ -z "$API_KEY" ]; then
    echo "DEEPSEEK_API_KEY=" > .env
    echo "  (未配置 API Key，翻译功能将不可用)"
else
    echo "DEEPSEEK_API_KEY=$API_KEY" > .env
    echo "  API Key 已配置"
fi

# 5. 创建 systemd 服务（开机自启）
echo "[5/6] 配置 systemd 服务..."
sudo cat > /etc/systemd/system/e-listening.service << EOF
[Unit]
Description=English Listening Training App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/E_listening
ExecStart=/opt/E_listening/.venv/bin/python app.py
Restart=always
RestartSec=5
Environment=HF_ENDPOINT=https://hf-mirror.com
Environment=HF_HUB_DISABLE_XET=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable e-listening
sudo systemctl restart e-listening

# 6. 检查状态
echo "[6/6] 检查服务状态..."
sleep 3
if sudo systemctl is-active --quiet e-listening; then
    echo "✅ 部署成功！"
else
    echo "❌ 服务启动失败，查看日志："
    sudo journalctl -u e-listening -n 30 --no-pager
    exit 1
fi

echo ""
echo "===== 部署完成 ====="
echo "访问地址: http://101.133.166.23:8001"
echo ""
echo "常用命令:"
echo "  查看状态:  sudo systemctl status e-listening"
echo "  查看日志:  sudo journalctl -u e-listening -f"
echo "  重启服务:  sudo systemctl restart e-listening"
echo "  停止服务:  sudo systemctl stop e-listening"
echo ""
echo "⚠️  别忘了在阿里云控制台安全组中放行 8001 端口！"
