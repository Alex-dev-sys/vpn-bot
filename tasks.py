"""
Фоновые задачи для бота
"""
import asyncio
from aiogram import Bot

from config import ADMIN_ID, PERIOD_NAMES, PERIOD_DAYS, OS_NAMES, OS_EMOJIS, APP_LINKS, get_instructions, logger
from database import Database
from outline_api import outline_manager
from payments import payment_manager
from keyboards import get_no_subscription_keyboard

db = Database()

async def check_payments(bot: Bot):
    """Проверка поступления оплаты (YooMoney)"""
    while True:
        try:
            pending_subs = await db.get_subscriptions_by_status('pending')
            
            for sub in pending_subs:
                # Проверяем в YooMoney по ID подписки (label) и сумме
                if payment_manager.check_payment(str(sub['id']), expected_amount=sub['price']):
                    logger.info(f"Payment confirmed for sub #{sub['id']}")
                    
                    # 1. Обновляем статус
                    await db.update_subscription_status(sub['id'], 'paid')
                    
                    # 2. Активируем подписку и выдаем ключ
                    server_id = sub['server_id']
                    user_id = sub['user_id']
                    os_type = sub['os']
                    days = PERIOD_DAYS.get(sub['period'], 30)
                    
                    key_data = await outline_manager.create_key(server_id, user_id)
                    
                    if key_data:
                        # Сохраняем и активируем
                        await db.activate_subscription_outline(
                            sub_id=sub['id'],
                            server_id=server_id,
                            outline_key_id=key_data['outline_key_id'],
                            access_url=key_data['access_url'],
                            days=days
                        )
                        
                        # Отправляем пользователю
                        instructions = get_instructions(os_type)
                        app_link = APP_LINKS.get(os_type, '')
                        
                        text = (
                            f"✅ *Оплата получена!*\n"
                            f"🚀 *Ваш доступ готов!*\n\n"
                            f"🌍 Локация: {key_data.get('server_flag', '🌍')} {key_data.get('server_location', '')}\n"
                            f"📱 Устройство: {OS_EMOJIS.get(os_type, '')} {OS_NAMES.get(os_type, os_type)}\n\n"
                            f"👇 *Нажмите на ключ, чтобы скопировать:*\n"
                            f"`{key_data['access_url']}`\n\n"
                            f"📚 *Инструкция:*\n"
                            f"1. Скачайте Outline: {app_link}\n"
                            f"2. Скопируйте ключ выше.\n"
                            f"3. Откройте приложение — оно само предложит добавить сервер.\n"
                            f"4. Нажмите ПOДКЛЮЧИТЬ.\n\n"
                            f"⚡ Приятного полёта!"
                        )
                        
                        try:
                            # Генерируем и отправляем QR-код
                            from utils.qr import generate_key_qr
                            from aiogram.types import BufferedInputFile
                            qr_image = generate_key_qr(
                                key_data['access_url'], 
                                key_data.get('server_location', ''), 
                                key_data.get('server_flag', '🌍')
                            )
                            await bot.send_photo(
                                user_id,
                                BufferedInputFile(qr_image.read(), filename="vpn_key.png"),
                                caption="📱 Отсканируйте QR-код в Outline"
                            )
                        except Exception as e:
                            logger.warning(f"QR generation failed: {e}")
                        
                        try:
                            await bot.send_message(user_id, text, parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"Failed to send key to user {user_id}: {e}")
                            
                        # Уведомляем админа
                        if ADMIN_ID:
                            try:
                                await bot.send_message(ADMIN_ID, f"💰 Заказ #{sub['id']} оплачен и выдан автоматически (YooMoney).")
                            except: pass
                            
                    else:
                        logger.error(f"Failed to generate key for paid sub #{sub['id']}")
                        # Уведомляем админа о сбое
                        if ADMIN_ID:
                             await bot.send_message(ADMIN_ID, f"⚠️ Заказ #{sub['id']} ОПЛАЧЕН, но не удалось создать ключ! Проверьте логи.")
                
                # Небольшая задержка между проверками разных сабов, чтобы не спамить API
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error in check_payments: {e}")

        # Проверяем каждые 30 секунд
        await asyncio.sleep(30)


async def check_subscriptions(bot: Bot):
    """Проверка истекающих и истекших подписок"""
    while True:
        try:
            # 1. Удаляем ключи истекших подписок
            expired = await db.get_expired_subscriptions_with_keys()
            for sub in expired:
                # Удаляем ключ с Outline сервера
                if sub.get('outline_key_id') and sub.get('server_id'):
                    server = outline_manager.get_server(sub['server_id'])
                    if server:
                        deleted = await server.delete_access_key(sub['outline_key_id'])
                        if deleted:
                            logger.info(f"Deleted key {sub['outline_key_id']} for expired sub #{sub['id']}")
                
                # Помечаем как истекшую
                await db.expire_subscription(sub['id'])
                
                # Уведомляем пользователя
                try:
                    await bot.send_message(
                        sub['user_id'],
                        "⛔ *Доступ приостановлен*\n\n"
                        "Ваша подписка истекла, и ключ был деактивирован.\n"
                        "Чтобы вернуться в сеть, просто оформите новую подписку.",
                        reply_markup=get_no_subscription_keyboard(),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify user {sub['user_id']}: {e}")
            
            # 2. Отправляем напоминания за 3 дня
            expiring = await db.get_expiring_subscriptions_not_reminded(days=3)
            for sub in expiring:
                try:
                    period = PERIOD_NAMES.get(sub['period'], sub['period'])
                    
                    # Кнопка продления со скидкой
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    renew_kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔥 Продлить -10%", callback_data="renew_discount")],
                        [InlineKeyboardButton(text="💳 Купить обычно", callback_data="buy_vpn")]
                    ])
                    
                    await bot.send_message(
                        sub['user_id'],
                        f"⏳ *VPN скоро отключится*\n\n"
                        f"Ваша подписка ({period}) истекает через 3 дня.\n\n"
                        f"🎁 *Специально для вас:* продлите сейчас со скидкой *10%*!",
                        reply_markup=renew_kb,
                        parse_mode="Markdown"
                    )
                    await db.mark_reminder_sent(sub['id'])
                    logger.info(f"Sent reminder to user {sub['user_id']} for sub #{sub['id']}")
                except Exception as e:
                    logger.warning(f"Failed to send reminder to {sub['user_id']}: {e}")

        except Exception as e:
            logger.error(f"Error in check_subscriptions: {e}")

        # Проверяем каждый час
        await asyncio.sleep(3600)


async def monitor_servers(bot: Bot):
    """Мониторинг доступности серверов"""
    while True:
        try:
            for server_id, server in outline_manager.servers.items():
                is_available = await server.is_available()
                
                if not is_available:
                    logger.warning(f"Server {server.name} ({server.flag_emoji}) is OFFLINE!")
                    # Можно добавить уведомление админу
                    try:
                        await bot.send_message(
                            ADMIN_ID,
                            f"⚠️ *Сервер недоступен!*\n\n"
                            f"{server.flag_emoji} {server.name}\n"
                            f"📍 {server.location}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error in monitor_servers: {e}")

        # Проверяем каждые 5 минут
        await asyncio.sleep(300)
