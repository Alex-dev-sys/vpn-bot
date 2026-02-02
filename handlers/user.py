"""
Пользовательские обработчики VPN-бота 3.0
Автоматическая генерация ключей через Outline API
"""
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    ADMIN_ID, PAYMENT_CARD, PRICES, PERIOD_NAMES, PERIOD_DAYS,
    OS_NAMES, OS_EMOJIS, APP_LINKS, REFERRAL_BONUS_DAYS,
    BOT_USERNAME, TEXTS, get_instructions, logger
)
from database import Database
from payments import payment_manager
from keyboards import (
    get_main_menu, get_period_keyboard, get_servers_keyboard,
    get_os_keyboard, get_payment_keyboard, get_confirm_payment_keyboard,
    get_subscription_keyboard, get_no_subscription_keyboard,
    get_referral_keyboard, get_promo_keyboard, get_rating_keyboard,
    get_review_request_keyboard, get_back_to_main
)
from outline_api import outline_manager

router = Router()
db = Database()


# ==================== СОСТОЯНИЯ ====================

class OrderStates(StatesGroup):
    choosing_period = State()
    choosing_server = State()
    choosing_os = State()
    waiting_payment = State()


class SupportStates(StatesGroup):
    waiting_message = State()


class PromoStates(StatesGroup):
    waiting_code = State()


class ReviewStates(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()


# ==================== УТИЛИТЫ ====================

def get_referral_code_from_start(text: str) -> str | None:
    """Извлечь реферальный код из /start"""
    parts = text.split()
    if len(parts) > 1:
        param = parts[1]
        if param.startswith("ref_"):
            return param[4:]
    return None


def calculate_days_left(expires_at: str) -> int:
    """Вычислить оставшиеся дни"""
    try:
        exp = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
        return max(0, (exp - datetime.now()).days)
    except:
        return 0


# ==================== КОМАНДЫ ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка /start с реферальным кодом"""
    await state.clear()

    user = message.from_user
    ref_code = get_referral_code_from_start(message.text)

    # Создаём/получаем пользователя
    db_user = await db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        referrer_code=ref_code
    )

    # Проверяем активную подписку
    active_sub = await db.get_active_subscription(user.id)
    
    # Бонусное сообщение для нового реферала
    welcome_text = TEXTS['welcome']
    if db_user.get('is_new') and ref_code:
        from config import REFERRAL_NEW_USER_BONUS_DAYS
        welcome_text = (
            f"🎉 *Добро пожаловать!*\n\n"
            f"Вы пришли по приглашению друга и получаете бонус *+{REFERRAL_NEW_USER_BONUS_DAYS} дней* к первой подписке!\n\n"
            + TEXTS['welcome']
        )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(has_active_sub=bool(active_sub)),
        parse_mode="Markdown"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    help_text = (
        "📖 *Помощь*\n\n"
        "🔹 /start — главное меню\n"
        "🔹 /my — моя подписка\n"
        "🔹 /ref — реферальная программа\n"
        "🔹 /support — связаться с поддержкой\n\n"
        "💡 Выберите тариф, оплатите и получите ключ мгновенно!"
    )
    await message.answer(help_text, parse_mode="Markdown")


@router.message(Command("my"))
async def cmd_my(message: Message):
    """Моя подписка"""
    active_sub = await db.get_active_subscription(message.from_user.id)

    if active_sub:
        days_left = calculate_days_left(active_sub['expires_at'])
        exp_date = active_sub['expires_at'][:10] if active_sub['expires_at'] else "—"

        text = TEXTS['subscription_active'].format(
            server=f"{active_sub['flag_emoji']} {active_sub['server_name']}",
            days=days_left,
            date=exp_date
        )
        await message.answer(text, reply_markup=get_subscription_keyboard(active_sub['id']), parse_mode="Markdown")
    else:
        await message.answer(TEXTS['no_subscription'], reply_markup=get_no_subscription_keyboard(), parse_mode="Markdown")


@router.message(Command("ref"))
async def cmd_ref(message: Message):
    """Реферальная программа"""
    await show_referral(message.from_user.id, message)


@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Поддержка"""
    await message.answer(
        "💬 *Техподдержка*\n\n"
        "Опишите вашу проблему, и мы ответим в ближайшее время.",
        parse_mode="Markdown"
    )
    await state.set_state(SupportStates.waiting_message)


# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    active_sub = await db.get_active_subscription(callback.from_user.id)

    await callback.message.edit_text(
        TEXTS['welcome'],
        reply_markup=get_main_menu(has_active_sub=bool(active_sub)),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== ТРИАЛ ====================

@router.callback_query(F.data == "start_trial")
async def start_trial(callback: CallbackQuery, state: FSMContext, bot: Bot = None):
    """Начать триал — сразу выдаём ключ"""
    user_obj = callback.from_user
    user = await db.get_user(user_obj.id)

    if user and user['trial_used']:
        await callback.message.edit_text(
            TEXTS['trial_used'],
            reply_markup=get_period_keyboard(show_trial=False),
            parse_mode="Markdown"
        )
        await state.set_state(OrderStates.choosing_period)
        await callback.answer()
        return

    # Авто-выбор сервера
    best_server = await outline_manager.get_least_loaded_server()
    if not best_server:
        await callback.answer("❌ Нет доступных серверов", show_alert=True)
        return

    await db.get_or_create_user(user_obj.id, user_obj.username, user_obj.full_name)

    # Создаём подписку
    sub_id = await db.create_subscription(
        user_id=user_obj.id,
        period="trial",
        os="universal",
        price=0,
        is_trial=True,
        server_id=best_server.server_id
    )

    await db.mark_trial_used(user_obj.id)
    
    await callback.message.edit_text("⏳ Генерирую ключ...")
    
    # Генерируем ключ через Outline API
    key_data = await generate_outline_key(user_obj.id, best_server.server_id, sub_id, days=1)
    
    if key_data:
        # Проверяем реферала и начисляем бонус
        db_user = await db.get_user(user_obj.id)
        if db_user and db_user.get('referrer_id') and bot:
            await db.add_referral_reward(db_user['referrer_id'], user_obj.id, REFERRAL_BONUS_DAYS)
            try:
                await bot.send_message(
                    db_user['referrer_id'],
                    f"🎉 Ваш реферал активировал триал!\n"
                    f"Вам начислено *+{REFERRAL_BONUS_DAYS} дней* бонуса.",
                    parse_mode="Markdown"
                )
            except:
                pass

        await send_outline_key(callback.message, key_data, is_trial=True)
    else:
        await callback.message.edit_text(
            "❌ Ошибка генерации ключа. Попробуйте позже или напишите в поддержку.",
            reply_markup=get_back_to_main()
        )
    
    await state.clear()
    await callback.answer()


# ==================== ПОКУПКА ====================

@router.callback_query(F.data == "buy_vpn")
async def buy_vpn(callback: CallbackQuery, state: FSMContext):
    """Начать покупку"""
    user = await db.get_user(callback.from_user.id)
    show_trial = user and not user['trial_used']

    await callback.message.edit_text(
        TEXTS['choose_period'],
        reply_markup=get_period_keyboard(show_trial=show_trial),
        parse_mode="Markdown"
    )
    await state.set_state(OrderStates.choosing_period)
    await callback.answer()


@router.callback_query(F.data == "renew_discount")
async def renew_discount(callback: CallbackQuery, state: FSMContext):
    """Продление со скидкой 10%"""
    user = await db.get_user(callback.from_user.id)
    
    # Показываем тарифы со скидкой 10%
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    for period, base_price in PRICES.items():
        if period == 'trial':
            continue
        discounted = int(base_price * 0.9)  # -10%
        name = PERIOD_NAMES.get(period, period)
        buttons.append([InlineKeyboardButton(
            text=f"{name} — {discounted}₽ (было {base_price}₽)",
            callback_data=f"discount_{period}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    
    await callback.message.edit_text(
        "🔥 *Скидка 10% на продление!*\n\n"
        "Выберите тариф:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("discount_"))
async def choose_discount_period(callback: CallbackQuery, state: FSMContext):
    """Выбор тарифа со скидкой"""
    period = callback.data.replace("discount_", "")
    base_price = PRICES.get(period, 100)
    price = int(base_price * 0.9)  # -10%
    
    best_server = await outline_manager.get_least_loaded_server()
    if not best_server:
        await callback.answer("❌ Нет доступных серверов", show_alert=True)
        return

    await state.update_data(period=period, price=price, is_trial=False, server_id=best_server.server_id, is_discount=True)

    await callback.message.edit_text(
        TEXTS['choose_os'],
        reply_markup=get_os_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(OrderStates.choosing_os)
    await callback.answer()


@router.callback_query(F.data.startswith("period_"))
async def choose_period(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выбор тарифа — сразу к оплате (без выбора ОС)"""
    period = callback.data.replace("period_", "")

    if period == "trial":
        return await start_trial(callback, state, bot)

    price = PRICES.get(period, 100)
    
    # Авто-выбор сервера
    best_server = await outline_manager.get_least_loaded_server()
    if not best_server:
        await callback.answer("❌ Нет доступных серверов", show_alert=True)
        return

    user = callback.from_user
    await db.get_or_create_user(user.id, user.username, user.full_name)

    # Создаём подписку сразу
    sub_id = await db.create_subscription(
        user_id=user.id,
        period=period,
        os="universal",  # Outline ключи универсальные
        price=price,
        is_trial=False,
        server_id=best_server.server_id
    )

    period_name = PERIOD_NAMES.get(period, period)
    server = await db.get_server(best_server.server_id)

    # Генерируем ссылку на оплату
    label = str(sub_id)
    username = user.username or f"id{user.id}"
    payment_url = payment_manager.create_payment_link(price, label, f"VPN #{sub_id} @{username}")

    text = (
        f"✅ *Заказ #{sub_id} создан!*\n\n"
        f"📅 Тариф: {period_name}\n"
        f"🌍 Сервер: {server['flag_emoji']} {server['location']}\n"
        f"💰 К оплате: *{price}₽*\n\n"
    )
    
    if payment_url:
        text += "Нажмите *Оплатить* для автоматической выдачи ключа."
    else:
        text += "⏳ Оплата проверяется автоматически."

    await callback.message.edit_text(
        text,
        reply_markup=get_payment_keyboard(
            sub_id, price, 
            has_card=False,  # Не показываем карту
            payment_url=payment_url
        ),
        parse_mode="Markdown"
    )
    
    await state.update_data(sub_id=sub_id)
    await state.set_state(OrderStates.waiting_payment)
    await callback.answer()


@router.callback_query(F.data == "back_to_period")
async def back_to_period(callback: CallbackQuery, state: FSMContext):
    """Назад к выбору тарифа"""
    user = await db.get_user(callback.from_user.id)
    show_trial = user and not user['trial_used']

    await callback.message.edit_text(
        TEXTS['choose_period'],
        reply_markup=get_period_keyboard(show_trial=show_trial),
        parse_mode="Markdown"
    )
    await state.set_state(OrderStates.choosing_period)
    await callback.answer()





@router.callback_query(F.data.startswith("os_"))
async def choose_os(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выбор ОС и создание заказа"""
    os_type = callback.data.replace("os_", "")
    data = await state.get_data()

    period = data.get("period")
    price = data.get("price", 0)
    server_id = data.get("server_id")
    is_trial = data.get("is_trial", False)

    user = callback.from_user
    await db.get_or_create_user(user.id, user.username, user.full_name)

    # Создаём подписку
    sub_id = await db.create_subscription(
        user_id=user.id,
        period=period,
        os=os_type,
        price=price,
        is_trial=is_trial,
        server_id=server_id
    )

    if is_trial:
        # Триал — сразу активируем через Outline API
        await db.mark_trial_used(user.id)
        
        # Генерируем ключ через Outline API
        key_data = await generate_outline_key(user.id, server_id, sub_id, days=1)
        
        if key_data:
            # Проверяем реферала и начисляем бонус
            db_user = await db.get_user(user.id)
            if db_user and db_user['referrer_id']:
                await db.add_referral_reward(db_user['referrer_id'], user.id, REFERRAL_BONUS_DAYS)
                try:
                    await bot.send_message(
                        db_user['referrer_id'],
                        f"🎉 Ваш реферал активировал триал!\n"
                        f"Вам начислено *+{REFERRAL_BONUS_DAYS} дней* бонуса.",
                        parse_mode="Markdown"
                    )
                except:
                    pass

            await send_outline_key(callback.message, key_data, is_trial=True)
        else:
            # Fallback — старый способ через файлы
            key_file_id = await db.get_server_key(server_id, os_type)
            await db.activate_subscription(sub_id, server_id, days=1)
            server = await db.get_server(server_id)
            await send_vpn_key_legacy(callback, bot, server, os_type, key_file_id, is_trial=True)

    else:
        # Платный тариф — оплата через YooMoney
        await state.update_data(sub_id=sub_id)

        period_name = PERIOD_NAMES.get(period, period)
        server = await db.get_server(server_id)

        # Генерируем ссылку на оплату
        label = str(sub_id)
        username = user.username or f"id{user.id}"
        payment_url = payment_manager.create_payment_link(price, label, f"VPN #{sub_id} @{username}")

        text = (
            f"✅ *Заказ #{sub_id} создан!*\n\n"
            f"📅 Тариф: {period_name}\n"
            f"🌍 Сервер: {server['flag_emoji']} {server['location']}\n"
            f"📱 ОС: {OS_EMOJIS.get(os_type, '')} {OS_NAMES.get(os_type, os_type)}\n"
            f"💰 К оплате: *{price}₽*\n\n"
        )
        
        if payment_url:
            text += "Для автоматической выдачи ключа нажмите *Оплатить* ниже."
        elif PAYMENT_CARD:
            text += (
                f"💳 Переведите на карту:\n"
                f"`{PAYMENT_CARD}`\n\n"
                f"⚠️ Укажите в комментарии: `{sub_id}`\n\n"
                f"После оплаты нажмите «Я оплатил»"
            )
        else:
            text += "Свяжитесь с администратором для оплаты."

        await callback.message.edit_text(
            text,
            reply_markup=get_payment_keyboard(
                sub_id, price, 
                has_card=bool(PAYMENT_CARD) and not payment_url, 
                payment_url=payment_url
            ),
            parse_mode="Markdown"
        )
        
        # Если ссылка сгенерирована, админа можно не дергать или уведомлять "Ожидает оплаты"
        # Админа уведомим, чтобы был в курсе
        if ADMIN_ID and not payment_url: # Если автооплата есть, можно не спамить админу каждым заказом, либо спамить
            # Ладно, оставим уведомление, но пометим как Auto
             pass # Оставим как было или чуть изменим? Пусть уведомляет.

        await state.set_state(OrderStates.waiting_payment)

    await callback.answer()


# ==================== ГЕНЕРАЦИЯ КЛЮЧЕЙ OUTLINE ====================

async def generate_outline_key(user_id: int, server_id: int, sub_id: int, days: int) -> dict | None:
    """Генерация ключа через Outline API"""
    server = outline_manager.get_server(server_id)
    
    if not server:
        logger.warning(f"Outline server {server_id} not found in manager")
        return None
    
    try:
        key_data = await outline_manager.create_key(server_id, user_id)
        
        if key_data:
            # Устанавливаем лимит трафика 500 GB
            TRAFFIC_LIMIT_BYTES = 500 * 1024 * 1024 * 1024  # 500 GB
            await server.set_data_limit(key_data['outline_key_id'], TRAFFIC_LIMIT_BYTES)
            
            # Сохраняем в БД
            await db.activate_subscription_outline(
                sub_id=sub_id,
                server_id=server_id,
                outline_key_id=key_data['outline_key_id'],
                access_url=key_data['access_url'],
                days=days
            )
            
            logger.info(f"Generated Outline key for user {user_id} on server {server_id} (500GB limit)")
            return key_data
        
    except Exception as e:
        logger.error(f"Failed to generate Outline key: {e}")
    
    return None


async def send_outline_key(message, key_data: dict, is_trial: bool = False):
    """Отправка Outline ключа пользователю"""
    instructions = get_instructions()  # Универсальная инструкция
    
    trial_text = " (Тест 24ч)" if is_trial else ""
    
    text = (
        f"🚀 *Ваш VPN-ключ готов!*{trial_text}\n\n"
        f"🌍 Сервер: {key_data.get('server_flag', '🌍')} {key_data.get('server_location', '')}\n\n"
        f"{'─' * 20}\n\n"
        f"🔑 *Ваш ключ (нажмите чтобы скопировать):*\n"
        f"`{key_data['access_url']}`\n\n"
        f"{'─' * 20}\n\n"
        f"{instructions}\n\n"
        f"📲 *Скачать приложение:*\n"
        f"https://getoutline.org/get-started/\n\n"
        f"Спасибо за выбор! 💚"
    )
    
    if hasattr(message, 'edit_text'):
        await message.edit_text(text, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


async def send_vpn_key_legacy(callback: CallbackQuery, bot: Bot, 
                               server: dict, os_type: str, key_file_id: str,
                               is_trial: bool = False):
    """Отправка VPN ключа (fallback через файлы)"""
    instructions = get_instructions(os_type)
    app_link = APP_LINKS.get(os_type, '')

    trial_text = " (TEST 24h)" if is_trial else ""

    caption = (
        f"🚀 *Ваш конфиг файл готов!*{trial_text}\n\n"
        f"🌍 Локация: {server['flag_emoji']} {server['location']}\n"
        f"📱 Система: {OS_EMOJIS.get(os_type, '')} {OS_NAMES.get(os_type, os_type)}\n\n"
        f"📂 Откройте этот файл в приложении AmneziaWG или WireGuard.\n\n"
        f"⬇️ Скачать приложение:\n{app_link}\n\n"
        f"⚡ Приятного полёта!\n\n"
        f"⚠️ *Важно:* Ключ предназначен для одного устройства.\n"
        f"При обнаружении использования на нескольких устройствах ключ будет заблокирован."
    )

    try:
        user_id = callback.from_user.id if isinstance(callback, CallbackQuery) else callback.chat.id
        
        if key_file_id:
            try:
                await bot.send_photo(
                    user_id,
                    photo=key_file_id,
                    caption=caption,
                    parse_mode="Markdown"
                )
            except:
                await bot.send_document(
                    user_id,
                    document=key_file_id,
                    caption=caption,
                    parse_mode="Markdown"
                )
        else:
            if hasattr(callback, 'message'):
                await callback.message.edit_text(
                    caption + "\n\n⏳ Генерируем ключ... Пожалуйста, подождите.",
                    parse_mode="Markdown"
                )
            else:
                 await bot.send_message(user_id, caption + "\n\n⏳ Генерируем ключ... Пожалуйста, подождите.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка отправки ключа: {e}")


@router.callback_query(F.data.startswith("paid_"))
async def user_paid(callback: CallbackQuery, bot: Bot):
    """Пользователь нажал Я оплатил"""
    sub_id = int(callback.data.replace("paid_", ""))
    sub = await db.get_subscription(sub_id)

    if not sub:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    if sub['status'] != 'pending':
        await callback.answer("✅ Заказ уже обработан", show_alert=True)
        return

    # Проверяем через API
    if payment_manager.check_payment(str(sub_id)):
        # Оплата найдена!
        await callback.message.edit_text("🚀 Оплата прошла успешно! Высылаю настройки...")
        
        # Выдача ключа
        server = await db.get_server(sub['server_id'])
        days = PERIOD_DAYS.get(sub['period'], 30)
         # Обновляем статус
        await db.update_subscription_status(sub_id, 'paid')
        
        key_data = await generate_outline_key(sub['user_id'], sub['server_id'], sub_id, days)
        
        if key_data:
            await send_outline_key(callback.message, key_data)
            return
        else:
            # Fallback
            key_file_id = await db.get_server_key(sub['server_id'], sub['os'])
            if key_file_id:
                  await db.activate_subscription(sub_id, sub['server_id'], days)
                  await send_vpn_key_legacy(callback, bot, server, sub['os'], key_file_id)
                  return

    # Если не найдено автоматически
    await callback.message.edit_text(
        f"⏳ *Оплата проверяется...*\n\n"
        f"Обычно это занимает до 1 минуты.\n"
        f"Как только средства поступят, бот автоматически пришлет ключ.\n"
        f"Если возникла проблема — нажмите «SOS Поддержка».",
        reply_markup=get_confirm_payment_keyboard(sub_id),
        parse_mode="Markdown"
    )

    # Уведомляем админа только если нет YooMoney (ручная оплата)
    if ADMIN_ID and not payment_manager.wallet:
        user = callback.from_user
        from keyboards import get_admin_order_keyboard
        try:
            await bot.send_message(
                ADMIN_ID,
                f"💳 *Ручное подтверждение!*\n\n"
                f"🛒 Заказ #{sub_id}\n"
                f"👤 @{user.username or 'нет'}\n"
                f"💰 {sub['price']}₽\n\n"
                f"⚠️ Требуется проверка админа",
                reply_markup=get_admin_order_keyboard(sub_id, user.id),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления админа: {e}")

    await callback.answer()


# ==================== ПОДПИСКА ====================

@router.callback_query(F.data == "my_subscription")
async def my_subscription(callback: CallbackQuery):
    """Моя подписка"""
    active_sub = await db.get_active_subscription(callback.from_user.id)

    if active_sub:
        days_left = calculate_days_left(active_sub['expires_at'])
        exp_date = active_sub['expires_at'][:10] if active_sub['expires_at'] else "—"

        text = TEXTS['subscription_active'].format(
            server=f"{active_sub['flag_emoji']} {active_sub['server_name']}",
            days=days_left,
            date=exp_date
        )
        await callback.message.edit_text(
            text, 
            reply_markup=get_subscription_keyboard(active_sub['id']),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            TEXTS['no_subscription'], 
            reply_markup=get_no_subscription_keyboard(),
            parse_mode="Markdown"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("show_key_"))
async def show_key(callback: CallbackQuery, bot: Bot):
    """Показать ключ"""
    sub_id = int(callback.data.replace("show_key_", ""))
    sub = await db.get_subscription(sub_id)

    if not sub or sub['user_id'] != callback.from_user.id:
        await callback.answer("❌ Подписка не найдена", show_alert=True)
        return

    # Сначала проверяем Outline ключ
    outline_key = await db.get_subscription_outline_key(sub_id)
    
    if outline_key and outline_key.get('access_url'):
        server = await db.get_server(sub['server_id'])
        text = (
            f"🔑 *Ваш ключ доступа:*\n\n"
            f"🌍 {server['flag_emoji']} {server['location']}\n\n"
            f"`{outline_key['access_url']}`\n\n"
            f"👆 *Нажмите на ключ чтобы скопировать*"
        )
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.answer()
        return

    # Fallback — старый способ через файлы
    key_file_id = await db.get_server_key(sub['server_id'], sub['os'])

    if key_file_id:
        server = await db.get_server(sub['server_id'])
        caption = f"🔑 Ключ для {server['flag_emoji']} {server['location']}"

        try:
            await bot.send_photo(callback.from_user.id, photo=key_file_id, caption=caption)
        except:
            await bot.send_document(callback.from_user.id, document=key_file_id, caption=caption)

        await callback.answer()
    else:
        await callback.answer("❌ Ключ не найден", show_alert=True)


# ==================== СМЕНА СЕРВЕРА ====================

@router.callback_query(F.data.startswith("switch_server_"))
async def switch_server_menu(callback: CallbackQuery):
    """Меню выбора нового сервера"""
    sub_id = int(callback.data.replace("switch_server_", ""))
    
    servers = await db.get_available_servers()
    sub = await db.get_subscription(sub_id)
    
    if not servers:
        await callback.answer("❌ Нет доступных серверов", show_alert=True)
        return
    
    # Фильтруем только Outline серверы
    outline_servers = [s for s in servers if s.get('outline_api_url') and s['id'] != sub.get('server_id')]
    
    if not outline_servers:
        await callback.answer("ℹ️ Вы уже на лучшем сервере", show_alert=True)
        return
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for s in outline_servers:
        load = int((s['current_users'] / s['max_users']) * 100) if s['max_users'] > 0 else 0
        emoji = "🟢" if load < 60 else "🟡"
        text = f"{emoji} {s['flag_emoji']} {s['location']}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"new_server_{sub_id}_{s['id']}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="my_subscription")])
    
    await callback.message.edit_text(
        "🔄 *Смена сервера*\n\nВыберите новый сервер:\n_(текущий ключ будет заменён)_",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("new_server_"))
async def perform_server_switch(callback: CallbackQuery, bot: Bot):
    """Выполнить смену сервера"""
    parts = callback.data.replace("new_server_", "").split("_")
    sub_id, new_server_id = int(parts[0]), int(parts[1])
    
    sub = await db.get_subscription(sub_id)
    if not sub or sub['status'] != 'active':
        await callback.answer("❌ Подписка не найдена или не активна", show_alert=True)
        return
    
    await callback.message.edit_text("⏳ Создаю новый ключ...")
    
    # Удаляем старый ключ
    old_key = await db.get_subscription_outline_key(sub_id)
    if old_key and old_key.get('outline_key_id'):
        old_server = outline_manager.get_server(sub['server_id'])
        if old_server:
            await old_server.delete_access_key(old_key['outline_key_id'])
    
    # Создаём новый ключ
    # Используем функции из этого же модуля
    days_left = calculate_days_left(sub['expires_at'])
    
    key_data = await generate_outline_key(sub['user_id'], new_server_id, sub_id, days_left)
    
    if key_data:
        await callback.message.edit_text(
            f"✅ *Сервер изменён!*\n\n"
            f"🆕 Новый сервер: {key_data.get('server_flag', '🌍')} {key_data.get('server_location', '')}\n\n"
            f"🔑 *Ваш новый ключ:*\n`{key_data['access_url']}`",
            parse_mode="Markdown"
        )
        logger.info(f"User {sub['user_id']} switched server from {sub['server_id']} to {new_server_id}")
    else:
        await callback.message.edit_text("❌ Ошибка создания ключа. Обратитесь в поддержку.")
    
    await callback.answer()


# ==================== РЕФЕРАЛЫ ====================

@router.callback_query(F.data == "referral")
async def referral_menu(callback: CallbackQuery):
    """Реферальное меню"""
    await show_referral(callback.from_user.id, callback.message, edit=True)
    await callback.answer()


async def show_referral(user_id: int, message, edit: bool = False):
    """Показать реферальную информацию"""
    stats = await db.get_referral_stats(user_id)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{stats['referral_code']}"

    text = TEXTS['referral_info'].format(
        bonus=REFERRAL_BONUS_DAYS,
        link=link,
        count=stats['total_referrals'],
        days=stats['earned_days']
    )

    if edit:
        await message.edit_text(text, reply_markup=get_referral_keyboard(link), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=get_referral_keyboard(link), parse_mode="Markdown")


# ==================== ПРОМОКОД ====================

@router.callback_query(F.data == "promo_code")
async def promo_menu(callback: CallbackQuery, state: FSMContext):
    """Ввод промокода"""
    await callback.message.edit_text(
        "🎟 *Введите промокод:*",
        reply_markup=get_back_to_main(),
        parse_mode="Markdown"
    )
    await state.set_state(PromoStates.waiting_code)
    await callback.answer()


@router.message(PromoStates.waiting_code)
async def process_promo(message: Message, state: FSMContext):
    """Обработка промокода"""
    code = message.text.strip().upper()
    promo = await db.get_promo_code(code)

    if promo and promo['is_valid']:
        discount_text = ""
        if promo['discount_percent'] > 0:
            discount_text += f"🔥 Скидка: {promo['discount_percent']}%\n"
        if promo['bonus_days'] > 0:
            discount_text += f"🎁 Бонус: +{promo['bonus_days']} дней\n"

        await state.update_data(promo_code=code, promo_id=promo['id'])

        await message.answer(
            TEXTS['promo_applied'].format(code=code, discount=discount_text),
            reply_markup=get_promo_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            TEXTS['promo_invalid'],
            reply_markup=get_back_to_main(),
            parse_mode="Markdown"
        )

    await state.clear()


# ==================== ПОДДЕРЖКА ====================

@router.callback_query(F.data == "support")
async def support_menu(callback: CallbackQuery, state: FSMContext):
    """Поддержка"""
    await callback.message.edit_text(
        "💬 *Техподдержка*\n\n"
        "Опишите вашу проблему, и мы ответим в ближайшее время.",
        reply_markup=get_back_to_main(),
        parse_mode="Markdown"
    )
    await state.set_state(SupportStates.waiting_message)
    await callback.answer()


@router.message(SupportStates.waiting_message)
async def process_support(message: Message, state: FSMContext, bot: Bot):
    """Обработка обращения"""
    user = message.from_user

    if ADMIN_ID:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        reply_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Ответить", url=f"tg://user?id={user.id}")]
        ])

        text = (
            f"💬 *Обращение в поддержку*\n\n"
            f"👤 @{user.username or 'нет'} (ID: {user.id})\n"
            f"📛 {user.full_name}\n\n"
        )

        try:
            if message.text:
                text += f"💬 {message.text}"
                await bot.send_message(ADMIN_ID, text, reply_markup=reply_kb, parse_mode="Markdown")
            elif message.photo:
                await bot.send_photo(
                    ADMIN_ID, photo=message.photo[-1].file_id,
                    caption=text + "📸 Фото", reply_markup=reply_kb, parse_mode="Markdown"
                )
            elif message.document:
                await bot.send_document(
                    ADMIN_ID, document=message.document.file_id,
                    caption=text + "📄 Документ", reply_markup=reply_kb, parse_mode="Markdown"
                )

            await message.answer(
                "✅ Сообщение отправлено!\n\nМы ответим в ближайшее время.",
                reply_markup=get_back_to_main()
            )
        except Exception as e:
            logger.error(f"Ошибка отправки в поддержку: {e}")
            await message.answer("❌ Ошибка. Попробуйте позже.", reply_markup=get_back_to_main())
    else:
        await message.answer("❌ Поддержка временно недоступна.", reply_markup=get_back_to_main())

    await state.clear()


# ==================== ОТЗЫВЫ ====================

@router.callback_query(F.data.startswith("review_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    """Начать отзыв"""
    sub_id = int(callback.data.replace("review_", ""))

    if await db.has_review(sub_id):
        await callback.answer("✅ Вы уже оставили отзыв", show_alert=True)
        return

    await state.update_data(sub_id=sub_id)
    await callback.message.edit_text(
        "⭐ *Оцените наш сервис:*",
        reply_markup=get_rating_keyboard(),
        parse_mode="Markdown"
    )
    await state.set_state(ReviewStates.waiting_rating)
    await callback.answer()


@router.callback_query(F.data.startswith("rating_"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка оценки"""
    rating = int(callback.data.replace("rating_", ""))
    await state.update_data(rating=rating)

    await callback.message.edit_text(
        f"✅ Вы поставили {'⭐' * rating}\n\n"
        "💬 Напишите комментарий или /skip",
        parse_mode="Markdown"
    )
    await state.set_state(ReviewStates.waiting_comment)
    await callback.answer()


@router.message(ReviewStates.waiting_comment)
async def process_comment(message: Message, state: FSMContext, bot: Bot):
    """Обработка комментария"""
    data = await state.get_data()
    sub_id = data.get('sub_id')
    rating = data.get('rating')

    comment = None if message.text == "/skip" else message.text
    await db.add_review(sub_id, message.from_user.id, rating, comment)

    await message.answer(
        "🙏 Спасибо за отзыв!",
        reply_markup=get_back_to_main()
    )

    # Уведомляем админа
    if ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"⭐ *Новый отзыв*\n\n"
                f"{'⭐' * rating} ({rating}/5)\n"
                f"💬 {comment if comment else 'Без комментария'}\n"
                f"👤 {message.from_user.full_name}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления админа: {e}")

    await state.clear()
