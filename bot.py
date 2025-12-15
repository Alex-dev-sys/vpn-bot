import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Цены
PRICES = {
    "1_month": 100,
    "6_months": 500,
    "1_year": 1000
}

PERIOD_NAMES = {
    "1_month": "1 месяц",
    "6_months": "6 месяцев",
    "1_year": "1 год"
}

OS_NAMES = {
    "ios": "iOS",
    "windows": "Windows",
    "android": "Android"
}


class VPNOrder(StatesGroup):
    choosing_period = State()
    choosing_os = State()


def get_period_keyboard():
    """Клавиатура выбора срока"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц - 100₽", callback_data="period_1_month")],
        [InlineKeyboardButton(text="6 месяцев - 500₽", callback_data="period_6_months")],
        [InlineKeyboardButton(text="1 год - 1000₽", callback_data="period_1_year")]
    ])
    return keyboard


def get_os_keyboard():
    """Клавиатура выбора ОС"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="iOS", callback_data="os_ios")],
        [InlineKeyboardButton(text="Windows", callback_data="os_windows")],
        [InlineKeyboardButton(text="Android", callback_data="os_android")]
    ])
    return keyboard


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await state.clear()

    welcome_text = (
        "👋 Добро пожаловать в VPN-магазин!\n\n"
        "Здесь вы можете приобрести надежный VPN для безопасного "
        "и анонимного доступа в интернет.\n\n"
        "На какой срок вы хотите купить VPN?"
    )

    await message.answer(welcome_text, reply_markup=get_period_keyboard())
    await state.set_state(VPNOrder.choosing_period)


@dp.callback_query(F.data.startswith("period_"))
async def process_period(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора срока"""
    period = callback.data.replace("period_", "")
    await state.update_data(period=period)

    await callback.message.edit_text(
        "📱 Выберите вашу операционную систему:",
        reply_markup=get_os_keyboard()
    )
    await state.set_state(VPNOrder.choosing_os)
    await callback.answer()


@dp.callback_query(F.data.startswith("os_"))
async def process_os(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора ОС и отправка итога"""
    os_choice = callback.data.replace("os_", "")
    data = await state.get_data()
    period = data.get("period")

    price = PRICES[period]
    period_name = PERIOD_NAMES[period]
    os_name = OS_NAMES[os_choice]

    # Сообщение пользователю
    user_message = (
        f"✅ Ваш заказ:\n\n"
        f"📅 Срок: {period_name}\n"
        f"💻 Операционная система: {os_name}\n"
        f"💰 Стоимость: {price}₽\n\n"
        f"Ожидайте, администратор свяжется с вами для оплаты."
    )

    await callback.message.edit_text(user_message)

    # Уведомление админу
    user = callback.from_user
    username = f"@{user.username}" if user.username else f"ID: {user.id}"

    admin_message = (
        f"🛒 Новый заказ VPN!\n\n"
        f"👤 Пользователь: {username}\n"
        f"📛 Имя: {user.full_name}\n"
        f"🆔 ID: {user.id}\n"
        f"📅 Срок: {period_name}\n"
        f"💻 ОС: {os_name}\n"
        f"💰 Сумма: {price}₽"
    )

    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, admin_message)
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")

    await state.clear()
    await callback.answer()


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
