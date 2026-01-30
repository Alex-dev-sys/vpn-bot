"""
VPN-бот 3.0 — главный модуль
Автоматическая генерация и удаление ключей через Outline API
"""
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_ID, PAYMENT_CARD, logger
from database import Database
from handlers import user_router, admin_router, inline_router
from outline_api import outline_manager, init_outline_servers

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
db = Database()

# Регистрация роутеров
dp.include_router(user_router)
dp.include_router(admin_router)
dp.include_router(inline_router)


# ==================== ИНИЦИАЛИЗАЦИЯ OUTLINE СЕРВЕРОВ ====================

async def init_outline():
    """Инициализация Outline серверов из БД"""
    servers = await db.get_servers_with_outline()
    
    if not servers:
        logger.warning("No Outline servers configured")
        return
    
    init_outline_servers(servers)
    logger.info(f"Initialized {len(servers)} Outline server(s)")
    
    # Проверяем доступность
    for srv in servers:
        server = outline_manager.get_server(srv['id'])
        if server:
            available = await server.is_available()
            status = "✅ online" if available else "❌ offline"
            logger.info(f"  {srv['flag_emoji']} {srv['name']}: {status}")


# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 50)
    logger.info("VPN Bot 3.0 запускается...")
    logger.info("=" * 50)
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Payment card: {'настроена' if PAYMENT_CARD else 'НЕ настроена'}")

    # Инициализация БД
    await db.init_db()

    # Инициализируем Outline серверы
    await init_outline()
    
    # Запускаем фоновые задачи
    from tasks import check_subscriptions, check_payments, monitor_servers
    
    asyncio.create_task(check_subscriptions(bot))
    logger.info("✅ Subscription checker started (every 1 hour)")
    
    asyncio.create_task(monitor_servers(bot))
    logger.info("✅ Server monitor started (every 5 min)")
    
    asyncio.create_task(check_payments(bot))
    logger.info("✅ Payment checker started (every 30 sec)")

    logger.info("Bot is running!")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        from outline_api import close_client_session
        await close_client_session()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
