"""
Конфигурация VPN-бота 2.0
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

# ==================== ЛОГИРОВАНИЕ ====================

# Настройка форматтера
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Хендлер для файла с ротацией (макс 5 МБ, храним 3 файла)
file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(formatter)

# Хендлер для консоли (с принудительным UTF-8 для Windows)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# Настройка корневого логгера
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

# Фикс для Windows (если не был применен ранее)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logger = logging.getLogger('vpn_bot')

# ==================== ОСНОВНЫЕ НАСТРОЙКИ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "vpn_saler_digital_bot")

# Проверка токена
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in .env file!")
    sys.exit(1)

if not ADMIN_ID:
    logger.warning("ADMIN_ID not found in .env file!")

# ==================== ЦЕНЫ ====================

PRICES = {
    "trial": 0,        # Бесплатный триал
    "1_month": 100,
    "3_months": 250,   # Новый тариф
    "6_months": 450,   # Скидка
    "1_year": 800      # Большая скидка
}

PERIOD_NAMES = {
    "trial": "Триал 24ч",
    "1_month": "1 месяц",
    "3_months": "3 месяца",
    "6_months": "6 месяцев",
    "1_year": "1 год"
}

PERIOD_DAYS = {
    "trial": 1,
    "1_month": 30,
    "3_months": 90,
    "6_months": 180,
    "1_year": 365
}

OS_NAMES = {
    "ios": "iOS",
    "android": "Android",
    "windows": "Windows",
    "macos": "macOS",
    "linux": "Linux"
}

OS_EMOJIS = {
    "ios": "🍎",
    "android": "🤖",
    "windows": "💻",
    "macos": "🖥",
    "linux": "🐧"
}

# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

REFERRAL_BONUS_DAYS = 7  # Бонус за приглашённого друга
REFERRAL_NEW_USER_BONUS_DAYS = 3  # Бонус новому пользователю за регистрацию по ссылке

# ==================== ССЫЛКИ НА ПРИЛОЖЕНИЯ ====================

APP_LINKS = {
    'ios': 'https://apps.apple.com/app/id6478942365',
    'android': 'https://play.google.com/store/apps/details?id=org.amnezia.vpn',
    'windows': 'https://github.com/amnezia-vpn/amnezia-client/releases',
    'macos': 'https://github.com/amnezia-vpn/amnezia-client/releases',
    'linux': 'https://github.com/amnezia-vpn/amnezia-client/releases'
}

# ==================== ИНСТРУКЦИИ ====================

def get_instructions(os_type: str) -> str:
    """Получить инструкции для ОС"""
    instructions = {
        'ios': (
            "📱 *Инструкция для iOS:*\n"
            "1. Скачайте AmneziaVPN из App Store\n"
            "2. Откройте приложение\n"
            "3. Нажмите «Добавить конфигурацию»\n"
            "4. Отсканируйте QR-код\n"
            "5. Нажмите «Подключиться»"
        ),
        'android': (
            "📱 *Инструкция для Android:*\n"
            "1. Скачайте AmneziaVPN из Google Play\n"
            "2. Откройте приложение\n"
            "3. Нажмите «Добавить конфигурацию»\n"
            "4. Отсканируйте QR-код\n"
            "5. Нажмите «Подключиться»"
        ),
        'windows': (
            "💻 *Инструкция для Windows:*\n"
            "1. Скачайте AmneziaVPN по ссылке\n"
            "2. Установите и откройте\n"
            "3. Нажмите «Добавить конфигурацию»\n"
            "4. Загрузите файл или QR-код\n"
            "5. Нажмите «Подключиться»"
        ),
        'macos': (
            "🖥 *Инструкция для macOS:*\n"
            "1. Скачайте AmneziaVPN по ссылке\n"
            "2. Установите и откройте\n"
            "3. Нажмите «Добавить конфигурацию»\n"
            "4. Загрузите файл или QR-код\n"
            "5. Нажмите «Подключиться»"
        ),
        'linux': (
            "🐧 *Инструкция для Linux:*\n"
            "1. Скачайте AmneziaVPN по ссылке\n"
            "2. Установите и откройте\n"
            "3. Импортируйте конфигурацию\n"
            "4. Нажмите «Подключиться»"
        )
    }
    return instructions.get(os_type, instructions['windows'])

# ==================== ТЕКСТЫ ====================

TEXTS = {
    'welcome': (
        "👋 *Приветствую в AmneziaVPN Shop!*\n\n"
        "🚀 **Твой личный доступ к свободному интернету.**\n"
        "Мы предоставляем быстрый и надежный VPN на базе протокола Outline.\n\n"
        "💎 **Почему мы?**\n"
        "• Высокая скорость и стабильность\n"
        "• Работает Instagram, YouTube (4K), Netflix\n"
        "• Анонимность и отсутствие логов\n"
        "• 1 подписка = 1 устройство\n\n"
        "👇 *Начни прямо сейчас:*"
    ),
    'choose_period': (
        "📅 *Выбери свой тариф:*\n\n"
        "🔥 **ХИТ:** 1 год — максимальная выгода (-33%)\n"
        "⚡ **Популярный:** 3 месяца — оптимальный выбор\n\n"
        "💡 *Совет: чем длительнее подписка, тем ниже цена за месяц!*"
    ),
    'choose_server': (
        "🌍 *Выбери локацию:*\n\n"
        "Все наши серверы обеспечивают высокую скорость.\n"
        "Рекомендуем выбирать ближайшую к вам страну для минимального пинга."
    ),
    'choose_os': (
        "📱 *На каком устройстве будешь использовать?*\n\n"
        "Мы подготовим инструкцию специально для твоей системы."
    ),
    'trial_offer': (
        "🎁 *Тест-драйв VPN*\n\n"
        "Попробуй **24 часа бесплатно**, чтобы убедиться в качестве.\n"
        "Никаких привязок карты и скрытых условий."
    ),
    'trial_used': (
        "😅 *Хорошего понемногу!*\n\n"
        "Ты уже использовал пробный период.\n"
        "Оформи подписку, чтобы продолжить пользоваться интернетом без границ."
    ),
    'referral_info': (
        "💸 *Зарабатывай с нами!*\n\n"
        "Пригласи друга и получи **+{bonus} дней** премиума бесплатно!\n\n"
        "🔗 *Твоя ссылка для приглашения:*\n"
        "`{link}`\n\n"
        "📊 *Твоя статистика:*\n"
        "👥 Приглашено: {count}\n"
        "🎁 Заработано дней: {days}"
    ),
    'promo_applied': (
        "🎉 *Промокод активирован!*\n\n"
        "Код: `{code}`\n"
        "{discount}\n"
        "Приятного пользования!"
    ),
    'promo_invalid': (
        "❌ *Упс... Промокод не сработал.*\n\n"
        "Возможно, он истек или был введен с ошибкой.\n"
        "Попробуй еще раз или напиши в поддержку."
    ),
    'subscription_active': (
        "🟢 *Твоя подписка активна*\n\n"
        "🌍 Локация: {server}\n"
        "⏳ Осталось дней: *{days}*\n"
        "📅 Истекает: {date}\n\n"
        "Нужен ключ или настройка? Жми кнопки ниже👇"
    ),
    'no_subscription': (
        "😴 *Подписка не активна*\n\n"
        "Самое время это исправить! Выбери тариф и верни себе свободный интернет."
    )
}

# ==================== ПЛАТЁЖНЫЕ СИСТЕМЫ ====================

# YooKassa (опционально)
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")

# Telegram Stars (встроенные платежи)
ENABLE_STARS = os.getenv("ENABLE_STARS", "false").lower() == "true"

# ==================== YOOMONEY ====================
YOOMONEY_TOKEN = os.getenv("YOOMONEY_TOKEN", "")
YOOMONEY_WALLET = os.getenv("YOOMONEY_WALLET", "")
