import asyncio
import csv
import os
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 386621236

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}
vacancies = []

def load_vacancies():
    global vacancies
    try:
        with open("vacancies.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            vacancies = list(reader)
        print(f"[INFO] Загружено {len(vacancies)} вакансий")
    except FileNotFoundError:
        vacancies = []
        print("[INFO] vacancies.csv не найден")

def log_application(data: dict, status: str, note: str = ""):
    log_exists = os.path.isfile("applications_log.csv")
    with open("applications_log.csv", "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not log_exists:
            writer.writerow(["Дата", "ФИО", "Возраст", "Телефон", "Город", "График", "Смена", "Статус", "Примечание"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"),
                         data.get("fio", "-"), data.get("age", "-"), data.get("phone", "-"),
                         data.get("city", "-"), data.get("schedule", "-"),
                         data.get("shift", "-"), status, note])

def find_vacancies(city: str, schedule: str):
    city = city.lower()
    schedule = schedule.lower()
    result = []
    for v in vacancies:
        if v["Город"].lower() == city:
            if "день" in schedule and int(v.get("День", 0)) > 0:
                result.append(v)
            elif "ноч" in schedule and int(v.get("Ночь", 0)) > 0:
                result.append(v)
    return result

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="☕ Заполнить анкету")]], resize_keyboard=True)
    await message.answer(
        "Привет! Я HR бот сети кофеен Кофемашина, рад твоему сообщению!\n"
        "Заполни пожалуйста небольшую анкету и я сориентирую тебя по свободным вакансиям.",
        reply_markup=kb)

@dp.message(lambda msg: msg.text == "☕ Заполнить анкету")
async def start_survey(message: types.Message):
    user_data[message.from_user.id] = {}
    await message.answer("Отправь своё ФИО:")

@dp.message(lambda msg: msg.from_user.id in user_data and "fio" not in user_data[msg.from_user.id])
async def fio_step(message: types.Message):
    user_data[message.from_user.id]["fio"] = message.text
    await message.answer("Введи возраст числом:")

@dp.message(lambda msg: "fio" in user_data.get(msg.from_user.id, {}) and "age" not in user_data[msg.from_user.id])
async def age_step(message: types.Message):
    data = user_data[message.from_user.id]
    try:
        age = int(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введи возраст числом.")
        return
    if age < 18:
        await message.answer("К сожалению, мы принимаем только кандидатов от 18 лет ☕")
        await bot.send_message(ADMIN_ID, f"❌ Отказ кандидату: {data['fio']} (возраст {age})")
        log_application(data, "Отказ", "Возраст < 18")
        user_data.pop(message.from_user.id, None)
        return
    data["age"] = age
    await message.answer("Введи свой номер телефона:")

@dp.message(lambda msg: "age" in user_data.get(msg.from_user.id, {}) and "phone" not in user_data[msg.from_user.id])
async def phone_step(message: types.Message):
    user_data[message.from_user.id]["phone"] = message.text
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=c)] for c in
                  ["Владивосток", "Артем", "Лучегорск", "Находка", "Южно-Сахалинск",
                   "Кипарисово", "Шмаковка", "Дальнегорск", "Уссурийск"]],
        resize_keyboard=True)
    await message.answer("В каком городе проживаешь?", reply_markup=kb)

@dp.message(lambda msg: "phone" in user_data.get(msg.from_user.id, {}) and "city" not in user_data[msg.from_user.id])
async def city_step(message: types.Message):
    user_data[message.from_user.id]["city"] = message.text
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Дневные"), KeyboardButton(text="Ночные")]], resize_keyboard=True)
    await message.answer("Какой график тебе подходит — дневные или ночные смены?", reply_markup=kb)

@dp.message(lambda msg: "city" in user_data.get(msg.from_user.id, {}) and "schedule" not in user_data[msg.from_user.id])
async def schedule_step(message: types.Message):
    schedule = message.text.lower()
    user_data[message.from_user.id]["schedule"] = schedule
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Полный"), KeyboardButton(text="Неполный")]], resize_keyboard=True)
    await message.answer("Ты рассматриваешь полный или неполный график?", reply_markup=kb)

@dp.message(lambda msg: "schedule" in user_data.get(msg.from_user.id, {}) and "shift" not in user_data[msg.from_user.id])
async def shift_step(message: types.Message):
    data = user_data[message.from_user.id]
    if message.text.lower().startswith("непол"):
        await message.answer("Укажи время смены (например, 10:00-17:00):")
        data["type"] = "неполный"
        return
    data["type"] = "полный"
    await finish_survey(message)

@dp.message(lambda msg: "type" in user_data.get(msg.from_user.id, {}) and user_data[msg.from_user.id]["type"] == "неполный" and "shift" not in user_data[msg.from_user.id])
async def shift_time_step(message: types.Message):
    text = message.text.strip()
    match = re.match(r"(\d{1,2}):?(\d{0,2})\s*[-–]\s*(\d{1,2}):?(\d{0,2})", text)
    if not match:
        await message.answer("Формат времени не распознан. Пример: 10:00-17:00")
        return
    start_h, start_m, end_h, end_m = match.groups()
    start_h, end_h = int(start_h), int(end_h)
    start_m, end_m = int(start_m or 0), int(end_m or 0)
    duration = (end_h * 60 + end_m) - (start_h * 60 + start_m)
    if duration < 6 * 60:
        await message.answer("Смена должна быть не менее 6 часов ☕")
        return
    user_data[message.from_user.id]["shift"] = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
    await finish_survey(message)

async def finish_survey(message: types.Message):
    data = user_data[message.from_user.id]
    city, schedule = data.get("city"), data.get("schedule")
    matches = find_vacancies(city, schedule)
    if matches:
        options = "\n".join([f"{v['Кофейня']} — {v['Адрес']}" for v in matches])
        await message.answer(f"Вот подходящие кофейни в {city}:\n\n{options}\n\nВыбери удобную:")
        data["awaiting_choice"] = True
    else:
        await message.answer("Пока нет открытых вакансий в твоём городе 😔")
        await bot.send_message(ADMIN_ID, f"📋 Анкета без вакансий:\n{data}")
        log_application(data, "Без подходящих вакансий")
        user_data.pop(message.from_user.id, None)

@dp.message(lambda msg: user_data.get(msg.from_user.id, {}).get("awaiting_choice"))
async def choose_cafe(message: types.Message):
    data = user_data[message.from_user.id]
    data["chosen_cafe"] = message.text
    await message.answer("Спасибо! Я передал твою анкету менеджеру ☕")
    await bot.send_message(ADMIN_ID, f"📋 Новая анкета:\n{data}")
    log_application(data, "Отправлена админу")
    user_data.pop(message.from_user.id, None)

async def on_startup():
    load_vacancies()
    print("Бот запущен!")

async def web_server():
    async def handle(request):
        return web.Response(text="Bot is running!")
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    return app

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling(bot, on_startup=on_startup))
    app = loop.run_until_complete(web_server())
    web.run_app(app, port=int(os.getenv("PORT", 8080)))
