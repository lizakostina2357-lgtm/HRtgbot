import asyncio
import logging
import csv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# === Настройки ===
TOKEN = "8469560301:AAE8ICqpKGb07JL7X4514BNcN215UDuAqwM"
ADMIN_ID = 386621236

# === Инициализация ===
bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# === Клавиатуры ===
def city_keyboard():
    buttons = [
        ["Владивосток", "Артем", "Лучегорск"],
        ["Находка", "Южно-Сахалинск", "Кипарисово"],
        ["Шмаковка", "Дальнегорск", "Уссурийск"]
    ]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=b)] for row in buttons for b in row], resize_keyboard=True)

def schedule_keyboard():
    buttons = [
        ["Дневные", "Ночные"],
        ["Полные", "Неполные"]
    ]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=b)] for row in buttons for b in row], resize_keyboard=True)

# === Хранилище анкет ===
user_data = {}

# === Старт анкеты ===
@dp.message(F.text & ~F.text.startswith('/'))
async def start_survey(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
        await message.answer(
            "Привет! Я HR бот сети кофеен Кофемашина ☕\nРад твоему сообщению! "
            "Заполни небольшую анкету, чтобы я сориентировал тебя по вакансиям."
        )
        await message.answer("Отправь своё ФИО:")
        return
    await message.answer("Продолжим анкету. Отправь своё ФИО:")

@dp.message(F.text & ~F.text.startswith('/'), F.from_user.id.in_(user_data))
async def handle_input(message: types.Message):
    user_id = message.from_user.id
    state = user_data[user_id]
    
    if 'name' not in state:
        state['name'] = message.text
        await message.answer("Введи свой возраст числом:")
        return

    if 'age' not in state:
        try:
            age = int(message.text)
            if age < 18:
                await message.answer("К сожалению, мы не можем принять тебя — минимальный возраст 18 лет.")
                user_data.pop(user_id, None)
                return
            state['age'] = age
            await message.answer("Введи свой номер телефона:")
        except ValueError:
            await message.answer("Пожалуйста, введи возраст числом.")
        return

    if 'phone' not in state:
        state['phone'] = message.text
        await message.answer("В каком городе проживаешь?", reply_markup=city_keyboard())
        return

    if 'city' not in state:
        state['city'] = message.text
        await message.answer("Какой график рассматриваешь?", reply_markup=schedule_keyboard())
        return

    if 'schedule' not in state:
        state['schedule'] = message.text
        await process_form(message, user_id)

async def process_form(message: types.Message, user_id):
    data = user_data[user_id]
    data['id'] = user_id

    # Сохранение анкеты в CSV
    with open('applications_log.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([data['id'], data['name'], data['age'], data['phone'], data['city'], data['schedule']])

    # Отправляем админу
    text = (
        f"📋 Новая анкета:\n"
        f"Имя: {data['name']}\nВозраст: {data['age']}\n"
        f"Телефон: {data['phone']}\nГород: {data['city']}\nГрафик: {data['schedule']}"
    )
    await bot.send_message(ADMIN_ID, text)

    # Отправляем пользователю вакансии
    vacancies = get_vacancies_for_city(data['city'], data['schedule'])
    if vacancies:
        await message.answer("Вот доступные вакансии в твоем городе:")
        for v in vacancies:
            await message.answer(f"🏠 {v['address']} — {v['position']} ({v['schedule']})")
    else:
        await message.answer("Пока нет открытых вакансий в твоем городе.")
    user_data.pop(user_id, None)

# === Работа с вакансиями ===
def get_vacancies_for_city(city, schedule):
    results = []
    try:
        with open('vacancies.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['city'].lower() == city.lower() and schedule.lower() in row['schedule'].lower():
                    results.append(row)
    except Exception as e:
        logging.error(f"Ошибка чтения файла вакансий: {e}")
    return results

# === Админские команды ===
@dp.message(Command("addfaq"))
async def add_faq(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Функция добавления FAQ пока не активна.")

@dp.message(Command("update_vacancies"))
async def update_vacancies(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Файл вакансий обновлён!")

# === Веб-сервер для Render ===
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_webserver():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

# === Запуск ===
async def main():
    asyncio.create_task(start_webserver())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
