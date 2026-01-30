"""
Клавиатуры для VPN-бота 2.0
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import PRICES, PERIOD_NAMES, OS_NAMES, OS_EMOJIS


# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_menu(has_active_sub: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    buttons = []
    
    if has_active_sub:
        buttons.append([InlineKeyboardButton(text="📊 Моя подписка", callback_data="my_subscription")])
    else:
        buttons.append([InlineKeyboardButton(text="🚀 Попробовать бесплатно", callback_data="start_trial")])
    
    buttons.extend([
        [InlineKeyboardButton(text="💎 Купить VPN", callback_data="buy_vpn")],
        [
            InlineKeyboardButton(text="💸 Заработать", callback_data="referral"),
            InlineKeyboardButton(text="🎟 Промокод", callback_data="promo_code")
        ],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_main() -> InlineKeyboardMarkup:
    """Кнопка назад в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


# ==================== ТАРИФЫ ====================

def get_period_keyboard(show_trial: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура выбора тарифа"""
    buttons = []
    
    if show_trial:
        buttons.append([InlineKeyboardButton(
            text="🎁 Тест-драйв 24ч (0₽)", 
            callback_data="period_trial"
        )])
    
    buttons.extend([
        [InlineKeyboardButton(
            text=f"📅 1 месяц — {PRICES['1_month']}₽", 
            callback_data="period_1_month"
        )],
        [InlineKeyboardButton(
            text=f"⚡ 3 месяца — {PRICES['3_months']}₽ (ХИТ)", 
            callback_data="period_3_months"
        )],
        [InlineKeyboardButton(
            text=f"📅 6 месяцев — {PRICES['6_months']}₽ (-25%)", 
            callback_data="period_6_months"
        )],
        [InlineKeyboardButton(
            text=f"🔥 1 год — {PRICES['1_year']}₽ (Выгодно)", 
            callback_data="period_1_year"
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== СЕРВЕРЫ ====================

def get_servers_keyboard(servers: list, callback_prefix: str = "server") -> InlineKeyboardMarkup:
    """Клавиатура выбора сервера"""
    buttons = []
    
    for server in servers:
        load = int((server['current_users'] / server['max_users']) * 100) if server['max_users'] > 0 else 0
        
        if load >= 90:
            load_emoji = "🔴"
        elif load >= 60:
            load_emoji = "🟡"
        else:
            load_emoji = "🟢"
        
        text = f"{server['flag_emoji']} {server['location']} {load_emoji}"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"{callback_prefix}_{server['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_period")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ОС ====================

def get_os_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора ОС"""
    buttons = [
        [
            InlineKeyboardButton(text=f"{OS_EMOJIS['ios']} iOS (iPhone/iPad)", callback_data="os_ios"),
            InlineKeyboardButton(text=f"{OS_EMOJIS['android']} Android", callback_data="os_android")
        ],
        [
            InlineKeyboardButton(text=f"{OS_EMOJIS['windows']} Windows", callback_data="os_windows"),
            InlineKeyboardButton(text=f"{OS_EMOJIS['macos']} macOS", callback_data="os_macos")
        ],
        [InlineKeyboardButton(text=f"{OS_EMOJIS['linux']} Linux", callback_data="os_linux")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_period")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== ОПЛАТА ====================

def get_payment_keyboard(sub_id: int, amount: int, has_card: bool = True, payment_url: str = None) -> InlineKeyboardMarkup:
    """Клавиатура оплаты"""
    buttons = []
    
    if payment_url:
        buttons.append([InlineKeyboardButton(
            text="💎 Оплатить (YooMoney)", 
            url=payment_url
        )])
    elif has_card:
        buttons.append([InlineKeyboardButton(
            text="💳 Перевод на карту", 
            callback_data=f"pay_card_{sub_id}"
        )])
    
    buttons.extend([
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{sub_id}")],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data="support")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_payment_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """Клавиатура после оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Купить еще", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
    ])


# ==================== ПОДПИСКА ====================

def get_subscription_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления подпиской"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Мой ключ", callback_data=f"show_key_{sub_id}")],
        [InlineKeyboardButton(text="🔄 Сменить сервер", callback_data=f"switch_server_{sub_id}")],
        [InlineKeyboardButton(text="⚡ Продлить подписку", callback_data="buy_vpn")],
        [
            InlineKeyboardButton(text="💸 Заработать", callback_data="referral"),
            InlineKeyboardButton(text="🆘 Помощь", callback_data="support")
        ],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu")]
    ])


def get_no_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура когда нет подписки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Попробовать бесплатно", callback_data="start_trial")],
        [InlineKeyboardButton(text="💳 Купить VPN", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


# ==================== РЕФЕРАЛЫ ====================

def get_referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    """Клавиатура реферальной программы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", switch_inline_query=referral_link)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


# ==================== ПРОМОКОД ====================

def get_promo_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после ввода промокода"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить со скидкой", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


# ==================== ОТЗЫВЫ ====================

def get_rating_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оценки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐", callback_data="rating_1"),
            InlineKeyboardButton(text="⭐⭐", callback_data="rating_2"),
            InlineKeyboardButton(text="⭐⭐⭐", callback_data="rating_3")
        ],
        [
            InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rating_4"),
            InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rating_5")
        ]
    ])


def get_review_request_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """Клавиатура запроса отзыва"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"review_{sub_id}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])


# ==================== АДМИН ====================

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура админ-панели"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖥 Серверы", callback_data="admin_servers")
        ],
        [
            InlineKeyboardButton(text="📋 Ожидают", callback_data="admin_pending"),
            InlineKeyboardButton(text="💰 Оплачено", callback_data="admin_paid")
        ],
        [
            InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promos"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="⭐ Отзывы", callback_data="admin_reviews"),
            InlineKeyboardButton(text="📈 Аналитика", callback_data="admin_analytics")
        ]
    ])


def get_admin_order_keyboard(sub_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для заказа (админ)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Написать", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_{sub_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_pending")]
    ])


def get_admin_servers_keyboard(servers: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора сервера для выдачи ключа"""
    buttons = []
    
    for server in servers:
        text = f"{server['flag_emoji']} {server['name']} ({server['current_users']}/{server['max_users']})"
        buttons.append([InlineKeyboardButton(
            text=text,
            callback_data=f"assign_{server['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_paid")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_promo_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления промокодами"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_add_promo")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_list_promos")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
    ])
