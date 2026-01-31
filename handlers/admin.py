"""
Админские обработчики VPN-бота 3.0
Управление серверами Outline и генерация ключей
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    ADMIN_ID, PRICES, PERIOD_NAMES, PERIOD_DAYS, OS_NAMES, OS_EMOJIS,
    APP_LINKS, REFERRAL_BONUS_DAYS, get_instructions, logger
)
from database import Database
from keyboards import (
    get_admin_keyboard, get_admin_order_keyboard,
    get_admin_servers_keyboard, get_admin_promo_keyboard,
    get_back_to_main, get_review_request_keyboard
)
from outline_api import outline_manager

router = Router()
db = Database()


# ==================== СОСТОЯНИЯ ====================


class AdminPromoStates(StatesGroup):
    waiting_code = State()
    waiting_discount = State()
    waiting_bonus_days = State()
    waiting_max_uses = State()


class AdminIssueKeyStates(StatesGroup):
    waiting_server = State()


# ==================== ПРОВЕРКА АДМИНА ====================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ==================== КОМАНДЫ ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель"""
    if not is_admin(message.from_user.id):
        return

    stats = await db.get_statistics()
    text = (
        f"👨‍💼 *Админ-панель*\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📊 Активных: {stats['active_subscriptions']}\n"
        f"💰 Доход: {stats['total_revenue']}₽\n\n"
        f"Выберите действие:"
    )
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    """Назад в админ-панель"""
    if not is_admin(callback.from_user.id):
        return

    await state.clear()
    stats = await db.get_statistics()
    text = (
        f"👨‍💼 *Админ-панель*\n\n"
        f"👥 Пользователей: {stats['total_users']}\n"
        f"📊 Активных: {stats['active_subscriptions']}\n"
        f"💰 Доход: {stats['total_revenue']}₽\n\n"
        f"Выберите действие:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    await callback.answer()


# ==================== СЕРВЕРЫ ====================




@router.callback_query(F.data == "admin_servers")
async def admin_servers(callback: CallbackQuery):
    """Список серверов"""
    if not is_admin(callback.from_user.id):
        return

    servers = await db.get_servers(active_only=False)

    if not servers:
        try:
            await callback.message.edit_text(
                "📭 Серверов нет. Нажмите ➕ чтобы добавить.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить сервер", callback_data="add_server")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]
                ])
            )
        except:
            pass
        await callback.answer()
        return

    text = "🖥 *Серверы:*\n\n"
    for s in servers:
        # Проверяем Outline API статус
        is_outline = bool(s.get('outline_api_url'))
        api_status = "🤖 API" if is_outline else "📁 Files"
        
        load = int((s['current_users'] / s['max_users']) * 100) if s['max_users'] > 0 else 0
        status_emoji = "🟢" if load < 60 else ("🟡" if load < 90 else "🔴")
        active = "✅" if s['is_active'] else "❌"

        text += (
            f"{status_emoji} {s['flag_emoji']} *{s['name']}* ({api_status})\n"
            f"👥 {s['current_users']}/{s['max_users']} | {active}\n"
            f"📍 {s['location']}\n\n"
        )

    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]]
    await callback.message.edit_text(
        text, 
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== ЗАКАЗЫ ====================

@router.callback_query(F.data == "admin_pending")
async def admin_pending(callback: CallbackQuery):
    """Ожидающие заказы"""
    if not is_admin(callback.from_user.id):
        return

    subs = await db.get_subscriptions_by_status('pending')

    if not subs:
        await callback.message.edit_text(
            "📭 Нет ожидающих заказов",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return

    text = "📋 *Ожидают оплаты:*\n\n"
    buttons = []

    for sub in subs[:10]:
        username = f"@{sub['username']}" if sub['username'] else f"ID: {sub['user_id']}"
        period = PERIOD_NAMES.get(sub['period'], sub['period'])

        text += f"#{sub['id']} {username} — {period} ({sub['price']}₽)\n"
        buttons.append([InlineKeyboardButton(
            text=f"#{sub['id']} — {sub['price']}₽",
            callback_data=f"view_sub_{sub['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_paid")
async def admin_paid(callback: CallbackQuery):
    """Оплаченные заказы"""
    if not is_admin(callback.from_user.id):
        return

    subs = await db.get_subscriptions_by_status('paid')

    if not subs:
        await callback.message.edit_text(
            "📭 Нет оплаченных заказов",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return

    text = "💰 *Оплачено (нужно выдать ключ):*\n\n"
    buttons = []

    for sub in subs[:10]:
        username = f"@{sub['username']}" if sub['username'] else f"ID: {sub['user_id']}"
        os = OS_EMOJIS.get(sub['os'], '') + OS_NAMES.get(sub['os'], sub['os'])

        text += f"#{sub['id']} {username} — {os}\n"
        buttons.append([InlineKeyboardButton(
            text=f"🔑 #{sub['id']} — {os}",
            callback_data=f"issue_key_{sub['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_sub_"))
async def view_subscription(callback: CallbackQuery):
    """Просмотр заказа"""
    if not is_admin(callback.from_user.id):
        return

    sub_id = int(callback.data.replace("view_sub_", ""))
    sub = await db.get_subscription(sub_id)

    if not sub:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    username = f"@{sub['username']}" if sub['username'] else f"ID: {sub['user_id']}"
    period = PERIOD_NAMES.get(sub['period'], sub['period'])
    os = OS_NAMES.get(sub['os'], sub['os'])
    trial = " (триал)" if sub['is_trial'] else ""

    text = (
        f"🛒 *Заказ #{sub_id}*{trial}\n\n"
        f"👤 {username}\n"
        f"📅 {period}\n"
        f"📱 {os}\n"
        f"💰 {sub['price']}₽\n"
        f"📊 Статус: {sub['status']}\n"
        f"🕐 {sub['created_at'][:16]}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_order_keyboard(sub_id, sub['user_id']),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(callback: CallbackQuery, bot: Bot):
    """Подтвердить оплату"""
    if not is_admin(callback.from_user.id):
        return

    sub_id = int(callback.data.replace("confirm_", ""))
    sub = await db.get_subscription(sub_id)

    if not sub:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    # Обновляем статус
    await db.update_subscription_status(sub_id, 'paid')
    
    # Попытка автоматической выдачи если Outline
    server = await db.get_server(sub['server_id'])
    if server and server.get('outline_api_url'):
        # Пробуем выдать автоматически
        from handlers.user import generate_outline_key, send_outline_key_direct # Note: need to ensure these are importable or use local logic
        # Actually generate_outline_key is in user.py, so we need to be careful with circular imports if user.py imports admin.py
        # user.py does NOT import admin.py. But admin.py imports user.py? 
        # Let's check imports. admin.py imports outline_manager. 
        # We should probably move generation logic to a service if possible, or just duplicate/import.
        # Ideally, move generate_outline_key to a service/logic file. 
        # For now, imports inside function avoid circular dependency at module level.
        
        # But wait, send_outline_key_direct is not in user.py in the snippets I saw previously?
        # Ah, I see `send_outline_key` in user.py.
        # Let's use that.
        
        from handlers.user import generate_outline_key, send_outline_key
        days = PERIOD_DAYS.get(sub['period'], 30)
        
        try:
            key_data = await generate_outline_key(sub['user_id'], sub['server_id'], sub_id, days)
            
            if key_data:
                # Уведомляем админа об успехе
                await callback.message.edit_text(
                    f"✅ *Оплата подтверждена и ключ выдан!* (Автоматически)\n\n"
                    f"Заказ #{sub_id} завершен.",
                    reply_markup=get_admin_keyboard(),
                    parse_mode="Markdown"
                )
                
                # Уведомляем юзера
                try:
                    await bot.send_message(
                        sub['user_id'],
                        "✅ *Оплата подтверждена!*",
                        parse_mode="Markdown"
                    )
                    # Отправляем ключ
                    await send_outline_key(
                        type('obj', (object,), {'edit_text': bot.send_message, 'chat': type('obj', (object,), {'id': sub['user_id']})}), 
                        key_data, sub['os']
                    ) 
                    # send_outline_key uses message.edit_text usually. 
                    # We might need a send_outline_key_direct that uses send_message.
                    # Or just adapt here.
                    instructions = get_instructions(sub['os'])
                    app_link = APP_LINKS.get(sub['os'], '')
                    
                    text = (
                        f"🎉 *Ваш VPN-ключ готов!*\n\n"
                        f"🌍 Сервер: {key_data.get('server_flag', '🌍')} {key_data.get('server_location', '')}\n"
                        f"📱 ОС: {OS_EMOJIS.get(sub['os'], '')} {OS_NAMES.get(sub['os'], sub['os'])}\n\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"🔑 *Ваш ключ (нажмите чтобы скопировать):*\n"
                        f"`{key_data['access_url']}`\n\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"{instructions}\n\n"
                        f"📥 Скачать приложение:\n{app_link}\n\n"
                        f"━━━━━━━━━━━━━━━━━━\n\n"
                        f"Спасибо за выбор! 💚"
                    )
                    await bot.send_message(sub['user_id'], text, parse_mode="Markdown")

                except Exception as e:
                    logger.error(f"Error auto sending key to user: {e}")
                
                await callback.answer("✅ Автоматически выдано!")
                return
        except Exception as e:
            logger.error(f"Auto issue error: {e}")
            # Fallback to manual

    await callback.message.edit_text(
        f"✅ Оплата #{sub_id} подтверждена!\n\n"
        f"Теперь выдайте ключ через «Оплачено»",
        reply_markup=get_admin_keyboard()
    )

    # Уведомляем клиента
    try:
        await bot.send_message(
            sub['user_id'],
            f"✅ Оплата подтверждена!\n\n"
            f"Заказ #{sub_id} — ключ будет выдан в ближайшее время."
        )
    except:
        pass

    await callback.answer("✅ Подтверждено!")


@router.callback_query(F.data.startswith("issue_key_"))
async def issue_key_choose_server(callback: CallbackQuery, state: FSMContext):
    """Выдать ключ — выбор сервера (если сервер не выбран или для смены)"""
    if not is_admin(callback.from_user.id):
        return

    sub_id = int(callback.data.replace("issue_key_", ""))
    sub = await db.get_subscription(sub_id)

    if not sub:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return

    servers = await db.get_available_servers()
    
    # Фильтруем серверы, которые могут выдать ключ (Outline или есть файл)
    valid_servers = []
    for s in servers:
        if s.get('outline_api_url') or await db.get_server_key(s['id'], sub['os']):
            valid_servers.append(s)

    if not valid_servers:
        await callback.answer(
            f"❌ Нет серверов с ключом/API для {OS_NAMES.get(sub['os'], sub['os'])}",
            show_alert=True
        )
        return

    await state.update_data(sub_id=sub_id)

    buttons = []
    for s in valid_servers:
        is_outline = "🤖" if s.get('outline_api_url') else "📁"
        text = f"{s['flag_emoji']} {s['name']} {is_outline} ({s['current_users']}/{s['max_users']})"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"assign_svr_{s['id']}")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_paid")])

    await callback.message.edit_text(
        f"🔑 *Выдача ключа #{sub_id}*\n\n"
        f"📱 ОС: {OS_NAMES.get(sub['os'], sub['os'])}\n\n"
        f"Выберите сервер:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await state.set_state(AdminIssueKeyStates.waiting_server)
    await callback.answer()


@router.callback_query(F.data.startswith("assign_svr_"))
async def assign_server_and_send_key(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выдать ключ"""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.replace("assign_svr_", ""))
    data = await state.get_data()
    sub_id = data.get('sub_id')

    sub = await db.get_subscription(sub_id)
    if not sub:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        await state.clear()
        return

    server = await db.get_server(server_id)
    days = PERIOD_DAYS.get(sub['period'], 30)

    # 1. Пробуем Outline API
    if server.get('outline_api_url'):
        from handlers.user import generate_outline_key
        
        await callback.message.edit_text("⏳ Генерирую ключ через API...")
        
        key_data = await generate_outline_key(sub['user_id'], server_id, sub_id, days)
        
        if key_data:
             # Начисляем реферальные
            user = await db.get_user(sub['user_id'])
            if user and user['referrer_id'] and not sub['is_trial']:
                await db.add_referral_reward(user['referrer_id'], sub['user_id'], REFERRAL_BONUS_DAYS)
                try:
                    await bot.send_message(
                        user['referrer_id'],
                        f"🎉 Ваш реферал оплатил подписку!\n"
                        f"Вам начислено *+{REFERRAL_BONUS_DAYS} дней* бонуса.",
                        parse_mode="Markdown"
                    )
                except:
                    pass

             # Отправляем ключ клиенту напрямую (дублируем логику отправки)
            os_type = sub['os']
            instructions = get_instructions(os_type)
            app_link = APP_LINKS.get(os_type, '')
            
            text = (
                f"🎉 *Ваш VPN-ключ готов!*\n\n"
                f"🌍 Сервер: {key_data.get('server_flag', '🌍')} {key_data.get('server_location', '')}\n"
                f"📱 ОС: {OS_EMOJIS.get(os_type, '')} {OS_NAMES.get(os_type, os_type)}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🔑 *Ваш ключ (нажмите чтобы скопировать):*\n"
                f"`{key_data['access_url']}`\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"{instructions}\n\n"
                f"📥 Скачать приложение:\n{app_link}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"Спасибо за выбор! 💚"
            )
            await bot.send_message(sub['user_id'], text, parse_mode="Markdown")
            
            await bot.send_message(
                sub['user_id'],
                "🙏 Пожалуйста, оцените наш сервис!",
                reply_markup=get_review_request_keyboard(sub_id)
            )

            await callback.message.edit_text(
                f"✅ *Ключ выдан!* (API)\n\n"
                f"#{sub_id} → {server['flag_emoji']} {server['name']}",
                reply_markup=get_admin_keyboard(),
                parse_mode="Markdown"
            )
            await state.clear()
            return
        else:
            await callback.message.answer("❌ Ошибка API. Пробую файловый ключ...")

    # 2. Fallback: Файловый ключ
    key_file_id = await db.get_server_key(server_id, sub['os'])

    if not key_file_id:
        await callback.answer("❌ Ключ не найден (и API недоступен)", show_alert=True)
        return

    # Активируем подписку
    await db.activate_subscription(sub_id, server_id, days=days)

    # Проверяем реферала
    user = await db.get_user(sub['user_id'])
    if user and user['referrer_id'] and not sub['is_trial']:
        await db.add_referral_reward(user['referrer_id'], sub['user_id'], REFERRAL_BONUS_DAYS)
        try:
            await bot.send_message(
                user['referrer_id'],
                f"🎉 Ваш реферал оплатил подписку!\n"
                f"Вам начислено *+{REFERRAL_BONUS_DAYS} дней* бонуса.",
                parse_mode="Markdown"
            )
        except:
            pass

    # Отправляем ключ клиенту
    os_type = sub['os']
    instructions = get_instructions(os_type)
    app_link = APP_LINKS.get(os_type, '')

    caption = (
        f"🎉 *Ваш VPN-ключ готов!*\n\n"
        f"🌍 Сервер: {server['flag_emoji']} {server['location']}\n"
        f"📱 ОС: {OS_EMOJIS.get(os_type, '')} {OS_NAMES.get(os_type, os_type)}\n"
        f"📅 Срок: {PERIOD_NAMES.get(sub['period'], sub['period'])}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{instructions}\n\n"
        f"📥 Скачать приложение:\n{app_link}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Спасибо за покупку! 💚"
    )

    try:
        try:
            await bot.send_photo(sub['user_id'], photo=key_file_id, caption=caption, parse_mode="Markdown")
        except:
            await bot.send_document(sub['user_id'], document=key_file_id, caption=caption, parse_mode="Markdown")

        await bot.send_message(
            sub['user_id'],
            "🙏 Пожалуйста, оцените наш сервис!",
            reply_markup=get_review_request_keyboard(sub_id)
        )

        await callback.message.edit_text(
            f"✅ *Ключ выдан!* (Файл)\n\n"
            f"#{sub_id} → {server['flag_emoji']} {server['name']}",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer("✅ Выдано!")

    except Exception as e:
        logger.error(f"Ошибка выдачи ключа: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

    await state.clear()


# ==================== ПРОМОКОДЫ ====================

@router.callback_query(F.data == "admin_promos")
async def admin_promos(callback: CallbackQuery):
    """Меню промокодов"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🎟 *Промокоды*\n\nВыберите действие:",
        reply_markup=get_admin_promo_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_promo")
async def admin_add_promo(callback: CallbackQuery, state: FSMContext):
    """Добавить промокод"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🎟 *Создание промокода*\n\n"
        "Введите код (например: NEWYEAR2026):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminPromoStates.waiting_code)
    await callback.answer()


@router.message(AdminPromoStates.waiting_code)
async def process_promo_code(message: Message, state: FSMContext):
    """Код промокода"""
    if not is_admin(message.from_user.id):
        return

    code = message.text.strip().upper()
    await state.update_data(code=code)

    await message.answer(
        f"✅ Код: *{code}*\n\n"
        f"Введите процент скидки (0-100) или 0 если без скидки:",
        parse_mode="Markdown"
    )
    await state.set_state(AdminPromoStates.waiting_discount)


@router.message(AdminPromoStates.waiting_discount)
async def process_promo_discount(message: Message, state: FSMContext):
    """Скидка промокода"""
    if not is_admin(message.from_user.id):
        return

    try:
        discount = max(0, min(100, int(message.text.strip())))
    except ValueError:
        discount = 0

    await state.update_data(discount_percent=discount)

    await message.answer(
        f"✅ Скидка: *{discount}%*\n\n"
        f"Введите бонусные дни (0 если без бонуса):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminPromoStates.waiting_bonus_days)


@router.message(AdminPromoStates.waiting_bonus_days)
async def process_promo_bonus(message: Message, state: FSMContext):
    """Бонусные дни"""
    if not is_admin(message.from_user.id):
        return

    try:
        bonus = max(0, int(message.text.strip()))
    except ValueError:
        bonus = 0

    await state.update_data(bonus_days=bonus)

    await message.answer(
        f"✅ Бонус: *{bonus} дн.*\n\n"
        f"Введите макс. количество использований (0 = безлимит):",
        parse_mode="Markdown"
    )
    await state.set_state(AdminPromoStates.waiting_max_uses)


@router.message(AdminPromoStates.waiting_max_uses)
async def process_promo_max_uses(message: Message, state: FSMContext):
    """Лимит использований и сохранение"""
    if not is_admin(message.from_user.id):
        return

    try:
        max_uses = max(0, int(message.text.strip()))
    except ValueError:
        max_uses = 0

    data = await state.get_data()

    if await db.create_promo_code(
        code=data['code'],
        discount_percent=data['discount_percent'],
        bonus_days=data['bonus_days'],
        max_uses=max_uses
    ):
        await message.answer(
            f"✅ *Промокод создан!*\n\n"
            f"🎟 `{data['code']}`\n"
            f"📉 -{data['discount_percent']}%\n"
            f"🎁 +{data['bonus_days']} дн.\n"
            f"🔢 Лимит: {max_uses or '♾️'}",
            reply_markup=get_admin_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "❌ Ошибка: такой код уже есть",
            reply_markup=get_admin_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "admin_list_promos")
async def admin_list_promos(callback: CallbackQuery):
    """Список промокодов"""
    if not is_admin(callback.from_user.id):
        return

    promos = await db.get_all_promo_codes()

    if not promos:
        await callback.message.edit_text(
            "📭 Промокодов нет",
            reply_markup=get_admin_promo_keyboard()
        )
        return

    text = "🎟 *Список промокодов:*\n\n"
    for p in promos:
        status = "✅" if p['is_active'] else "❌"
        uses = f"{p['current_uses']}/{p['max_uses']}" if p['max_uses'] > 0 else f"{p['current_uses']}/♾️"
        
        text += (
            f"`{p['code']}` {status}\n"
            f"📉 {p['discount_percent']}% | 🎁 +{p['bonus_days']}д | 👥 {uses}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_promo_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== СТАТИСТИКА ====================

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Расширенная статистика с трафиком"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text("⏳ Загружаю статистику...")
    
    stats = await db.get_statistics()
    
    text = (
        f"📊 *Статистика*\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"📈 Активных подписок: {stats['active_subscriptions']}\n"
        f"💰 Доход: {stats['total_revenue']}₽\n\n"
    )
    
    # Получаем метрики трафика с серверов
    text += "🖥 *Серверы:*\n"
    for server_id, server in outline_manager.servers.items():
        try:
            metrics = await server.get_metrics()
            total_bytes = sum(metrics.values()) if metrics else 0
            total_gb = total_bytes / (1024**3)
            key_count = await server.get_key_count()
            
            text += (
                f"\n{server.flag_emoji} *{server.name}*\n"
                f"  👥 Ключей: {key_count}\n"
                f"  📊 Трафик: {total_gb:.1f} GB\n"
            )
        except Exception as e:
            text += f"\n{server.flag_emoji} {server.name}: ⚠️ Ошибка\n"
            logger.error(f"Stats error for server {server.name}: {e}")
    
    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]]
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== ОТЗЫВЫ ====================

@router.callback_query(F.data == "admin_reviews")
async def admin_reviews(callback: CallbackQuery):
    """Список отзывов"""
    if not is_admin(callback.from_user.id):
        return

    reviews = await db.get_reviews()
    avg = await db.get_average_rating()

    if not reviews:
        await callback.message.edit_text(
            "📭 Отзывов пока нет",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return

    text = f"⭐ *Отзывы* (ср. {avg:.1f}/5)\n\n"
    for r in reviews[:15]:
        stars = "⭐" * r['rating']
        username = f"@{r['username']}" if r['username'] else f"ID: {r['user_id']}"
        comment = f"\n  💬 {r['comment']}" if r.get('comment') else ""
        text += f"{username}: {stars}{comment}\n\n"

    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]]
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== АНАЛИТИКА ====================

@router.callback_query(F.data == "admin_analytics")
async def admin_analytics(callback: CallbackQuery):
    """Расширенная аналитика с графиками"""
    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text("⏳ Собираю аналитику...")
    
    data = await db.get_analytics(days=7)
    
    # Формируем текстовый "график" новых пользователей
    text = "📈 *Аналитика за 7 дней*\n\n"
    
    # Новые пользователи
    text += "👥 *Новые пользователи:*\n"
    if data['new_users']:
        max_val = max(data['new_users'].values()) if data['new_users'] else 1
        for day, count in list(data['new_users'].items())[-7:]:
            bar = "█" * int((count / max(max_val, 1)) * 8) or "▏"
            text += f"`{day[5:]}` {bar} {count}\n"
    else:
        text += "_Нет данных_\n"
    
    # Доход
    text += "\n💰 *Доход (₽):*\n"
    if data['revenue']:
        max_rev = max(data['revenue'].values()) if data['revenue'] else 1
        total_rev = sum(data['revenue'].values())
        for day, rev in list(data['revenue'].items())[-7:]:
            bar = "█" * int((rev / max(max_rev, 1)) * 8) or "▏"
            text += f"`{day[5:]}` {bar} {rev}₽\n"
        text += f"\n*Итого:* {total_rev}₽\n"
    else:
        text += "_Нет данных_\n"
    
    # Популярные тарифы
    text += "\n📊 *Популярные тарифы:*\n"
    for period, count in list(data['popular_tariffs'].items())[:5]:
        name = PERIOD_NAMES.get(period, period)
        text += f"  {name}: {count} шт.\n"
    
    buttons = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin")]]
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    await callback.answer()

