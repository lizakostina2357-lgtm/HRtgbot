import logging
import os
import re
import pandas as pd
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiohttp import web

# ====================== Настройки ======================
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 386621236
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://<your-app>.onrender.com

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

user_data = {}  # временное хранилище кандидатов

# ====================== Клавиатуры ======================
def city_keyboard():
    buttons = ["Владивосток", "Артем", "Лучегорск",
               "Находка", "Южно-Сахалинск", "Кипарисово",
               "Шмаковка", "Дальнегорск", "Уссурийск"]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=b)] for b in buttons],
        resize_keyboard=True
    )

def first_schedule_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="День")],
                  [KeyboardButton(text="Ночь")]],
        resize_keyboard=True
    )

def second_schedule_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Полные")],
                  [KeyboardButton(text="Неполные")]],
        resize_keyboard=True
    )

# ====================== Загрузка вакансий из Excel ======================
def load_vacancies():
    try:
        df = pd.read_excel("vacancies.xlsx")
        return df.to_dict(orient="records")
    except Exception as e:
        logging.warning(f"Ошибка загрузки вакансий: {e}")
        return []

vacancies = load_vacancies()

def find_vacancies(city: str, shift_type: str, full_or_partial: str):
    city = city.lower()
    shift_type = shift_type.lower()
    full_or_partial = full_or_partial.lower()
    results = []
    for v in vacancies:
        if v["Город"].lower() != city:
            continue
        if shift_type == "день" and int(v.get("День", 0)) == 0:
            continue
        if shift_type == "ночь" and int(v.get("Ночь", 0)) == 0:
            continue
        if full_or_partial == "неполные" and v.get("смежники", "нет").lower() != "да":
            continue
        results.append(v)
    return results

# ====================== Загрузка FAQ из Excel ======================
def load_faq():
    try:
        df = pd.read_excel("FAQ.xlsx")  # Две колонки: Вопрос, Ответ
        faq = {str(row["Вопрос"]).lower(): str(row["Ответ"]) for _, row in df.iterrows()}
        return faq
    except Exception as e:
        logging.warning(f"Ошибка загрузки FAQ: {e}")
        return {}

faq_dict = load_faq()

# ====================== Логирование ======================
def log_application(data: dict, status: str, note: str = ""):
    import csv
    log_exists = os.path.isfile("applications_log.csv")
    with open("applications_log.csv", "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not log_exists:
            writer.writerow(["ФИО", "Возраст", "Телефон", "Город", "Смены", "График", "Время", "Статус", "Примечание"])
        writer.writerow([
            data.get("fio", "-"),
            data.get("age", "-"),
            data.get("phone", "-"),
            data.get("city", "-"),
            f"{data.get('shift_type','-')}/{data.get('full_partial','-')}",
            data.get("full_partial","-"),
            data.get("schedule_time","-"),
            status,
            note
        ])

# ====================== Анкета ======================
async def ask_question(user_id, message, text, keyboard=None):
    await message.answer(text, reply_markup=keyboard)

async def start_survey(user_id, message):
    user_data[user_id] = {}
    await ask_question(user_id, message,
                       "Привет! Я HR-бот сети кофеен Кофемашина, рад твоему сообщению!\n"
                       "Заполни, пожалуйста, небольшую анкету.\n\nОтправь своё ФИО:")

@dp.message(types.ContentType.TEXT)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # ====================== Проверка FAQ ======================
    if text.lower() in faq_dict:
        await message.answer(faq_dict[text.lower()])
        return

    # ====================== Начало анкеты на любое первое сообщение ======================
    if user_id not in user_data:
        await start_survey(user_id, message)
        return

    state = user_data[user_id]

    if 'fio' not in state:
        state['fio'] = text
        await ask_question(user_id, message, "Сколько тебе лет?")
        return

    if 'age' not in state:
        try:
            age = int(text)
            if age < 18:
                await ask_question(user_id, message,
                                   "Спасибо за ответ! К сожалению, минимальный возраст 18 лет.")
                user_data.pop(user_id, None)
                return
            state['age'] = age
            await ask_question(user_id, message, "Напиши свой номер телефона:")
        except ValueError:
            await ask_question(user_id, message, "Пожалуйста, введи возраст числом.")
        return

    if 'phone' not in state:
        state['phone'] = text
        await ask_question(user_id, message, "В каком городе проживаешь?", city_keyboard())
        return

    if 'city' not in state:
        state['city'] = text
        await ask_question(user_id, message, "Выбери смену: день или ночь?", first_schedule_keyboard())
        return

    if 'shift_type' not in state:
        if text.lower() not in ["день", "ночь"]:
            await ask_question(user_id, message, "Пожалуйста, выбери день или ночь", first_schedule_keyboard())
            return
        state['shift_type'] = text
        await ask_question(user_id, message, "Полные или неполные смены?", second_schedule_keyboard())
        return

    if 'full_partial' not in state:
        if text.lower() not in ["полные", "неполные"]:
            await ask_question(user_id, message, "Выбери Полные или Неполные", second_schedule_keyboard())
            return
        state['full_partial'] = text
        await ask_question(user_id, message, "Укажи время смены, например 10:00-16:00:")
        return

    if 'schedule_time' not in state:
        match = re.match(r"(\d{1,2}):?(\d{0,2})\s*[-–]\s*(\d{1,2}):?(\d{0,2})", text)
        if not match:
            await ask_question(user_id, message, "Формат времени не распознан. Пример: 10:00-17:00")
            return
        start_h, start_m, end_h, end_m = match.groups()
        start_h, end_h = int(start_h), int(end_h)
        start_m, end_m = int(start_m or 0), int(end_m or 0)
        duration = (end_h*60+end_m) - (start_h*60+start_m)
        if state['full_partial'].lower() == "неполные" and duration < 6*60:
            await ask_question(user_id, message,
                               "К сожалению, смена должна быть не менее 6 часов для неполной смены. Попробуй другой вариант.")
            return
        state['schedule_time'] = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"

        matched = find_vacancies(state['city'], state['shift_type'], state['full_partial'])
        if not matched and state['full_partial'].lower() == "неполные":
            await ask_question(user_id, message,
                               "Спасибо! К сожалению, сейчас открытых вакансий на неполные смены нет. "
                               "Но напишем тебе, если появятся.")
            log_application(state, "Отказ - нет смежников")
            user_data.pop(user_id, None)
            return

        if matched:
            msg = "Вот доступные вакансии:\n"
            for v in matched:
                msg += f"{v['Кофейня']} — {v['Адрес']} ({v.get('schedule', '-')})\n"
            await ask_question(user_id, message, msg)
        else:
            await ask_question(user_id, message, "Пока нет подходящих вакансий.")

        log_application(state, "Анкета отправлена")
        await bot.
        send_message(ADMIN_ID, f"Новая анкета:\nФИО: {state['fio']}\nВозраст: {state['age']}\nТелефон: {state['phone']}\nГород: {state['city']}\nСмены: {state['shift_type']}/{state['full_partial']}\nВремя: {state['schedule_time']}")
        user_data.pop(user_id, None)
        return

# ====================== Webhook ======================
async def webhook_handler(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.process_update(update)
    return web.Response(text="OK")

app = web.Application()
app.router.add_post(WEBHOOK_PATH, webhook_handler)

async def on_startup(app):
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL не задан!")
    webhook_url = f"{WEBHOOK_URL}/webhook/{TOKEN}"
    await bot.set_webhook(webhook_url)

async def on_shutdown(app):
    await bot.delete_webhook()

app.on_startup.append(on_startup)
app.on_cleanup.append(on_shutdown)

if name == "__main__":
    import aiohttp
    import asyncio
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
