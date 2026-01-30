#!/bin/bash

# VPN Bot Deployment Script
# Автоматическое развертывание бота на VPS

set -e

VPS_IP="185.216.87.218"
VPS_USER="root"
BOT_DIR="/opt/vpn-bot"

echo "🚀 Starting VPN Bot deployment to $VPS_IP"

# Функция для выполнения команд на сервере
ssh_cmd() {
    ssh -o StrictHostKeyChecking=no ${VPS_USER}@${VPS_IP} "$1"
}

# 1. Установка зависимостей на сервере
echo "📦 Installing dependencies on VPS..."
ssh_cmd "apt-get update && apt-get install -y python3 python3-pip python3-venv git"

# 2. Создание директории для бота
echo "📁 Creating bot directory..."
ssh_cmd "mkdir -p ${BOT_DIR}"

# 3. Копирование файлов на сервер
echo "📤 Uploading files..."
scp -o StrictHostKeyChecking=no bot.py database.py requirements.txt .env ${VPS_USER}@${VPS_IP}:${BOT_DIR}/

# 4. Установка Python зависимостей
echo "🐍 Installing Python packages..."
ssh_cmd "cd ${BOT_DIR} && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"

# 5. Создание systemd service
echo "⚙️  Creating systemd service..."
ssh_cmd "cat > /etc/systemd/system/vpn-bot.service << 'EOF'
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${BOT_DIR}
Environment=\"PATH=${BOT_DIR}/venv/bin\"
ExecStart=${BOT_DIR}/venv/bin/python ${BOT_DIR}/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF"

# 6. Перезагрузка systemd и запуск бота
echo "🔄 Starting bot service..."
ssh_cmd "systemctl daemon-reload"
ssh_cmd "systemctl enable vpn-bot"
ssh_cmd "systemctl restart vpn-bot"

# 7. Проверка статуса
echo ""
echo "✅ Deployment completed!"
echo ""
echo "📊 Bot status:"
ssh_cmd "systemctl status vpn-bot --no-pager"

echo ""
echo "🎉 Bot is now running on VPS!"
echo ""
echo "Useful commands:"
echo "  View logs:    ssh ${VPS_USER}@${VPS_IP} 'journalctl -u vpn-bot -f'"
echo "  Stop bot:     ssh ${VPS_USER}@${VPS_IP} 'systemctl stop vpn-bot'"
echo "  Start bot:    ssh ${VPS_USER}@${VPS_IP} 'systemctl start vpn-bot'"
echo "  Restart bot:  ssh ${VPS_USER}@${VPS_IP} 'systemctl restart vpn-bot'"
