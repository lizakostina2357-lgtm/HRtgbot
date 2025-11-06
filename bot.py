import asyncio
import csv
import os
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}
vacancies = []
faq_data = []

def load_vacancies():
    global vacancies
    try:
        with open("vacancies.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            vacancies = list(reader)
        print(f"[INFO] Загружено {len(vacancies)} вакансий")
    except FileNotFoundError:
        vacancies = []

def log_application(data: dict, status: str, note: str = ""):
    log_exists = os.path.isfile("applications_log.csv")
    with open("applications_log.csv", "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not log_exists:
            writer.writerow(["Дата", "ФИО", "Возраст", "Телефон", "Город",
                             "График", "Смена", "Статус", "Примечание"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            data.get("fio", "-"),
            data.get("age", "-"),
            data.get("phone", "-"),
            data.get("city", "-"),
            data.get("schedule", "-"),
            data.get("shift", "-"),
            status,
            note
        ])

def load_faq():
    global faq_data
    try:
        with open("faq.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            faq_data = list(reader)
        print(f"[INFO] Загружено {len(faq_data)} FAQ")
    except FileNotFoundError:
        faq_data = []

def save_faq():
    with open("faq.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Вопрос", "Ответ"])
        writer.writeheader()
        writer.writerows(faq_data)

@dp.message(Command("faq"))
async def show_faq(message: types.Message):
    if not faq_data:
        await message.answer("FAQ пока пуст 😔")
        return
    text = "\n\n".join([f"❓ {item['Вопрос']}\n💬 {item['Ответ']}" for item in faq_data])
    await message.answer(text)

@dp.message(Command("add_faq"))
async def add_faq(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда только для администратора.")
        return
    user_data[message.from_user.id] = {"adding_faq": "question"}
    await message.answer("✏️ Напиши вопрос для FAQ:")

@dp.message(lambda msg: user_data.get(msg.from_user.id, {}).get("adding_faq") == "question")
async def add_faq_question(message: types.Message):
    user_data[message.from_user.id]["faq_question"] = message.text
    user_data[message.from_user.id]["adding_faq"] = "answer"
    await message.answer("📝 Теперь напиши ответ:")

@dp.message(lambda msg: user_data.get(msg.from_user.id, {}).get("adding_faq") == "answer")
async def add_faq_answer(message: types.Message):
    q = user_data[message.from_user.id]["faq_question"]
    a = message.text
    faq_data.append({"Вопрос": q, "Ответ": a})
    save_faq()
    user_data.pop(message.from_user.id, None)
    await message.answer("✅ Новый FAQ добавлен!")

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.lower()
    for item in faq_data:
        if item["Вопрос"].lower() in text:
            await message.answer(item["Ответ"])
            return
    await message.answer("Спасибо за сообщение! Я передал его менеджеру ☕")

async def handle_web(request):
    return web.Response(text="Bot is running ☕")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[INFO] Web server started on port {port}")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
