"""
Inline-режим — показ статуса подписки в любом чате
"""
from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from database import Database
from handlers.user import calculate_days_left

router = Router()
db = Database()


@router.inline_query()
async def inline_subscription_status(query: InlineQuery):
    """Показ статуса подписки через инлайн-запрос"""
    user_id = query.from_user.id
    active_sub = await db.get_active_subscription(user_id)
    
    results = []
    
    if active_sub:
        days_left = calculate_days_left(active_sub['expires_at'])
        exp_date = active_sub['expires_at'][:10] if active_sub['expires_at'] else "—"
        
        results.append(InlineQueryResultArticle(
            id="sub_status",
            title=f"✅ VPN активен — {days_left} дн.",
            description=f"Сервер: {active_sub.get('server_name', '—')} | До: {exp_date}",
            input_message_content=InputTextMessageContent(
                message_text=(
                    f"✅ *Мой VPN активен!*\n\n"
                    f"🌍 Сервер: {active_sub.get('flag_emoji', '🌍')} {active_sub.get('server_name', '—')}\n"
                    f"📅 Осталось: *{days_left}* дней\n"
                    f"🔒 Защита 24/7"
                ),
                parse_mode="Markdown"
            )
        ))
    else:
        results.append(InlineQueryResultArticle(
            id="no_sub",
            title="❌ Нет активной подписки",
            description="Нажмите, чтобы поделиться",
            input_message_content=InputTextMessageContent(
                message_text=(
                    "🔓 У меня пока нет VPN...\n\n"
                    "Хочешь попробовать? Регистрируйся и получи *бесплатный триал*!"
                ),
                parse_mode="Markdown"
            )
        ))
    
    await query.answer(results, cache_time=60, is_personal=True)
