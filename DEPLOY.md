# 🚀 Инструкция по развертыванию бота на VPS

## Подготовка

### 1. Настройка SSH ключей (рекомендуется)

Для удобства настрой SSH ключи, чтобы не вводить пароль каждый раз:

```bash
# Создай SSH ключ (если еще нет)
ssh-keygen -t rsa -b 4096

# Скопируй ключ на сервер
ssh-copy-id root@YOUR_SERVER_IP
```

### 2. Проверь .env файл

Убедись, что файл `.env` содержит правильные данные:
- BOT_TOKEN
- ADMIN_ID
- PAYMENT_CARD

## Автоматическое развертывание

### Вариант 1: Через Git Bash или WSL (Windows)

```bash
cd "c:/Users/user/OneDrive/Desktop/vpn bot/vpn-bot"
bash deploy.sh
```

### Вариант 2: Ручное развертывание

Если скрипт не работает, выполни команды вручную:

#### 1. Подключись к серверу
```bash
ssh root@YOUR_SERVER_IP
```

#### 2. Установи зависимости
```bash
apt-get update
apt-get install -y python3 python3-pip python3-venv
```

#### 3. Создай директорию для бота
```bash
mkdir -p /opt/vpn-bot
cd /opt/vpn-bot
```

#### 4. Загрузи файлы
С локального компьютера выполни:
```bash
scp bot.py database.py requirements.txt .env root@YOUR_SERVER_IP:/opt/vpn-bot/
```

#### 5. Установи Python зависимости
На сервере:
```bash
cd /opt/vpn-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### 6. Создай systemd service
```bash
cat > /etc/systemd/system/vpn-bot.service << 'EOF'
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/vpn-bot
Environment="PATH=/opt/vpn-bot/venv/bin"
ExecStart=/opt/vpn-bot/venv/bin/python /opt/vpn-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

#### 7. Запуск бота
```bash
systemctl daemon-reload
systemctl enable vpn-bot
systemctl start vpn-bot
```

#### 8. Проверь статус
```bash
systemctl status vpn-bot
```

## Полезные команды

### Просмотр логов
```bash
ssh root@YOUR_SERVER_IP 'journalctl -u vpn-bot -f'
```

### Перезапуск бота
```bash
ssh root@YOUR_SERVER_IP 'systemctl restart vpn-bot'
```

### Остановка бота
```bash
ssh root@YOUR_SERVER_IP 'systemctl stop vpn-bot'
```

### Обновление бота
```bash
# Загрузи новые файлы
scp bot.py database.py root@YOUR_SERVER_IP:/opt/vpn-bot/

# Перезапусти
ssh root@YOUR_SERVER_IP 'systemctl restart vpn-bot'
```

### Резервное копирование базы данных
```bash
scp root@YOUR_SERVER_IP:/opt/vpn-bot/vpn_bot.db ./vpn_bot_backup.db
```

## Troubleshooting

### Бот не запускается
```bash
# Проверь логи
ssh root@YOUR_SERVER_IP 'journalctl -u vpn-bot -n 50'

# Проверь, запущен ли процесс
ssh root@YOUR_SERVER_IP 'ps aux | grep bot.py'

# Попробуй запустить вручную
ssh root@YOUR_SERVER_IP
cd /opt/vpn-bot
source venv/bin/activate
python bot.py
```

### Ошибка подключения SSH
```bash
# Проверь SSH ключи
ssh-keygen -R YOUR_SERVER_IP
ssh root@YOUR_SERVER_IP
```

### Бот работает, но не отвечает
- Проверь, правильный ли BOT_TOKEN в .env
- Проверь, есть ли интернет на VPS
- Проверь логи на наличие ошибок

## Безопасность

### Рекомендуется:
1. Создай отдельного пользователя для бота (не root)
2. Настрой firewall (ufw)
3. Включи автоматические обновления Ubuntu
4. Регулярно делай бэкапы базы данных

### Создание пользователя для бота
```bash
adduser vpnbot
usermod -aG sudo vpnbot
# Измени User=root на User=vpnbot в service файле
```
