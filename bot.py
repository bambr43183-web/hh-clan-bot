import asyncio
import re
import sqlite3
from datetime import datetime, timedelta, time

from aiogram import Bot, Dispatcher, exceptions
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ================== НАЛАШТУВАННЯ ==================
TOKEN = "8404813322:AAHW1xd6eoo2SduUTAkYJ1dFaEFlXxxgiR0"  # < токен
CHAT_ID = -1002492131233        # ID чату
DB_NAME = "users.db"
# =================================================

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== БАЗА ДАНИХ ==================
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    name TEXT,
    age INTEGER,
    birth TEXT,
    city TEXT,
    nickname TEXT,
    game_id TEXT,
    inviter TEXT,
    last_birthday_year INTEGER
)
""")
conn.commit()

# ================== FSM ==================
class Form(StatesGroup):
    name = State()
    age = State()
    birth = State()
    city = State()
    nickname = State()
    game_id = State()
    inviter = State()

# ================== КОМАНДИ ==================
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Привіт!\n"
        "Я бот для реєстрації в клані та нагадувань 🎂\n"
        "Напиши /form щоб заповнити анкету"
    )

@dp.message(Command("form"))
async def form_start(message: Message, state: FSMContext):
    await message.answer("Введіть Ваше ім'я:")
    await state.set_state(Form.name)

# ================== АНКЕТА ==================
@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    if not re.match(r"^[A-Za-zА-Яа-яЁёЇїІіЄєҐґ\s-]+$", message.text):
        await message.answer("❌ Ім'я має містити тільки літери. Спробуйте ще раз:")
        return
    await state.update_data(name=message.text)
    await message.answer("Введіть Ваш вік:")
    await state.set_state(Form.age)

@dp.message(Form.age)
async def get_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Вік має бути числом:")
        return
    age = int(message.text)
    if age < 10 or age > 80:
        await message.answer("❌ Введіть реальний вік:")
        return
    await state.update_data(age=age)
    await message.answer("Введіть дату народження (дд.мм.рррр):")
    await state.set_state(Form.birth)

@dp.message(Form.birth)
async def get_birth(message: Message, state: FSMContext):
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", message.text):
        await message.answer("❌ Формат: дд.мм.рррр")
        return
    await state.update_data(birth=message.text)
    await message.answer("Введіть Ваше місто:")
    await state.set_state(Form.city)

@dp.message(Form.city)
async def get_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Введіть нік у грі:")
    await state.set_state(Form.nickname)

@dp.message(Form.nickname)
async def get_nickname(message: Message, state: FSMContext):
    await state.update_data(nickname=message.text)
    await message.answer("Введіть ігровий ID:")
    await state.set_state(Form.game_id)

@dp.message(Form.game_id)
async def get_game_id(message: Message, state: FSMContext):
    await state.update_data(game_id=message.text)
    await message.answer("Хто Вас запросив? (username без @):")
    await state.set_state(Form.inviter)

@dp.message(Form.inviter)
async def finish_form(message: Message, state: FSMContext):
    await state.update_data(inviter=message.text)
    data = await state.get_data()
    user = message.from_user
    year = datetime.now().year

    cursor.execute("""
    INSERT OR REPLACE INTO users
    (telegram_id, username, name, age, birth, city, nickname, game_id, inviter, last_birthday_year)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user.id,
        user.username,
        data["name"],
        data["age"],
        data["birth"],
        data["city"],
        data["nickname"],
        data["game_id"],
        data["inviter"],
        0
    ))
    conn.commit()

    text = (
        "📋 АНКЕТА ГРАВЦЯ\n\n"
        f"👤 Ім'я: {data['name']}\n"
        f"🎂 Вік: {data['age']}\n"
        f"📅 ДР: {data['birth']}\n"
        f"🏙 Місто: {data['city']}\n"
        f"🎮 Нік: {data['nickname']}\n"
        f"🆔 ID: {data['game_id']}\n"
        f"🤝 Хто привів: @{data['inviter']}\n\n"
        f"📱 Telegram: @{user.username}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Показати ігровий ID",
                callback_data=f"ID:{data['game_id']}"
            )]
        ]
    )

    await message.answer(text, reply_markup=keyboard)
    await bot.send_message(CHAT_ID, text)
    await state.clear()

# ================== CALLBACK ==================
@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    if callback.data.startswith("ID:"):
        await callback.message.answer(f"🆔 Ваш ігровий ID:\n{callback.data[3:]}")
    await callback.answer()

# ================== КОМАНДА /BIRTHDAYS ==================
@dp.message(Command("birthdays"))
async def show_birthdays(message: Message):
    today = datetime.now()
    upcoming = today + timedelta(days=7)
    text = "🎂 Дні народження найближчих 7 днів:\n\n"

    cursor.execute("SELECT name, username, birth FROM users")
    users = cursor.fetchall()
    found = False

    for name, username, birth in users:
        birth_date = datetime.strptime(birth, "%d.%m.%Y")
        birth_this_year = birth_date.replace(year=today.year)
        if today <= birth_this_year <= upcoming:
            text += f"{birth} — {name} (@{username})\n"
            found = True

    if not found:
        text += "Немає днів народження найближчим часом 😅"

    await message.answer(text)

# ================== ФОНОВИЙ ТАЙМЕР 14:00 ==================
async def birthday_scheduler():
    while True:
        now = datetime.now()
        target_time = datetime.combine(now.date(), time(14, 0))
        if now > target_time:
            target_time += timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        today_str = datetime.now().strftime("%d.%m")
        year = datetime.now().year

        cursor.execute("SELECT telegram_id, username, name, birth, last_birthday_year FROM users")
        users = cursor.fetchall()

        for tg_id, username, name, birth, last_year in users:
            if birth[:5] == today_str and last_year != year:
                text = f"🎉 Сьогодні день народження у {name}! 🎂\n@{username}"
                await bot.send_message(CHAT_ID, text)
                cursor.execute(
                    "UPDATE users SET last_birthday_year=? WHERE telegram_id=?",
                    (year, tg_id)
                )
                conn.commit()

# ================== НАДІЙНИЙ MAIN() ==================
async def main():
    # запускаємо фоновий таск для ДР
    asyncio.create_task(birthday_scheduler())

    while True:
        try:
            print("Бот стартує...")
            await dp.start_polling(bot)
        except exceptions.TelegramNetworkError:
            print("⚠️ Проблеми з мережею. Перепідключення через 5 секунд...")
            await asyncio.sleep(5)
        except exceptions.TelegramRetryAfter as e:
            print(f"⚠️ Telegram наказав чекати {e.timeout} секунд...")
            await asyncio.sleep(e.timeout)
        except Exception as e:
            print("❌ Невідома помилка:", e)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())