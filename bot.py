import asyncio
import csv
import os
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}
vacancies = []

# ---------------- ВАКАНСИИ ----------------

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


@dp.message(Command("update_vacancies"))
async def update_vacancies(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда только для администратора.")
        return
    await message.answer("Отправь CSV-файл с актуальными вакансиями.")


@dp.message(lambda msg: msg.document and msg.from_user.id == ADMIN_ID)
async def handle_file(message: types.Message):
    file = await bot.get_file(message.document.file_id)
    path = "vacancies.csv"
    await bot.download_file(file.file_path, path)
    load_vacancies()
    await message.answer("✅ Файл обновлён, вакансии загружены.")


def find_vacancies(city: str, schedule: str):
    city = city.lower()
    schedule = schedule.lower()
    result = []

    for v in vacancies:
        if v["Город"].lower() == city:
            if "день" in schedule and int(v["День"]) > 0:
                result.append(v)
            elif "ноч" in schedule and int(v["Ночь"]) > 0:
                result.append(v)
    return result

# ---------------- ЛОГИРОВАНИЕ ----------------

def log_application(data: dict, status: str, note: str = ""):
    log_exists = os.path.isfile("applications_log.csv")
    with open("applications_log.csv", "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not log_exists:
            writer.writerow(["Дата", "ФИО", "Возраст", "Телефон", "Город", "График", "Смена", "Статус", "Примечание"])
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

# ---------------- АНКЕТА ----------------

@dp.message(Command("start"))
async def start(message: types.Message):
    user_data[message.from_user.id] = {}
    await message.answer("Привет! Пожалуйста, введи своё ФИО:")


@dp.message(lambda msg: msg.from_user.id in user_data and "fio" not in user_data[msg.from_user.id])
async def fio_step(message: types.Message):
    user_data[message.from_user.id]["fio"] = message.text
    await message.answer("Сколько тебе лет?")


@dp.message(lambda msg: "fio" in user_data.get(msg.from_user.id, {}) and "age" not in user_data[msg.from_user.id])
async def age_step(message: types.Message):
    data = user_data[message.from_user.id]
    data["age"] = message.text

    try:
        age = int(data["age"])
    except ValueError:
        await message.answer("Пожалуйста, введи возраст числом.")
        return

    if age < 18:
        await message.answer(
            "Спасибо за ответ! К сожалению, пока не готовы рассмотреть тебя в команду, "
            "так как берём ребят от 18 лет, но давай не теряться! Как только тебе исполнится 18 — сразу пиши)
"
            "А пока будем ждать тебя в качестве гостя, хорошего тебе дня! 🌞"
        )
        await bot.send_message(
            ADMIN_ID,
            f"❌ Отказ кандидату\nФИО: {data['fio']}\nВозраст: {data['age']}\nПричина: Возраст < 18"
        )
        log_application(data, "Отказ", "Возраст < 18")
        user_data.pop(message.from_user.id, None)
        return

    await message.answer("Напиши свой номер телефона:")


@dp.message(lambda msg: "age" in user_data.get(msg.from_user.id, {}) and "phone" not in user_data[msg.from_user.id])
async def phone_step(message: types.Message):
    user_data[message.from_user.id]["phone"] = message.text
    await message.answer("Из какого ты города?")


@dp.message(lambda msg: "phone" in user_data.get(msg.from_user.id, {}) and "city" not in user_data[msg.from_user.id])
async def city_step(message: types.Message):
    user_data[message.from_user.id]["city"] = message.text
    await message.answer("Какой график тебе подходит? (полный / неполный / день / ночь)")


@dp.message(lambda msg: "city" in user_data.get(msg.from_user.id, {}) and "schedule" not in user_data[msg.from_user.id])
async def schedule_step(message: types.Message):
    schedule = message.text.lower()
    user_data[message.from_user.id]["schedule"] = schedule

    if "непол" in schedule:
        await message.answer("Со скольки до скольки ты готов(а) выходить в смены? (например, 10:00-16:00)")
    else:
        await finish_survey(message)


@dp.message(lambda msg: "schedule" in user_data.get(msg.from_user.id, {}) and "shift" not in user_data[msg.from_user.id])
async def shift_step(message: types.Message):
    if "непол" not in user_data[message.from_user.id]["schedule"]:
        return

    text = message.text.strip()
    match = re.match(r"(\d{1,2}):?(\d{0,2})\s*[-–]\s*(\d{1,2}):?(\d{0,2})", text)
    if not match:
        await message.answer("Формат времени не распознан. Пример: 10:00-17:00")
        return

    start_h, start_m, end_h, end_m = match.groups()
    start_h, end_h = int(start_h), int(end_h)
    start_m = int(start_m or 0)
    end_m = int(end_m or 0)

    duration = (end_h * 60 + end_m) - (start_h * 60 + start_m)
    if duration < 6 * 60:
        await message.answer("К сожалению, смена должна быть не менее 6 часов. Пожалуйста, напиши другой вариант.")
        return

    user_data[message.from_user.id]["shift"] = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
    await finish_survey(message)


async def finish_survey(message: types.Message):
    data = user_data[message.from_user.id]
    shift = data.get("shift", "—")

    matches = find_vacancies(data["city"], data["schedule"])
    if matches:
        options = "\n".join([f"{v['Кофейня']} — {v['Адрес']}" for v in matches])
        await message.answer(
            f"Могу предложить тебе эти кофейни в твоём городе:\n\n{options}\n\nКакая будет удобнее?"
        )
        data["awaiting_choice"] = True
    else:
        await message.answer("Пока нет открытых вакансий в твоём городе под этот график 😔")
        await bot.send_message(
            ADMIN_ID,
            f"📋 Анкета (без подходящих вакансий)\nФИО: {data['fio']}\nВозраст: {data['age']}\n"
            f"Город: {data['city']}\nГрафик: {data['schedule']}\nСмена: {shift}"
        )
        log_application(data, "Без подходящих вакансий")
        user_data.pop(message.from_user.id, None)


@dp.message(lambda msg: user_data.get(msg.from_user.id, {}).get("awaiting_choice"))
async def choose_cafe(message: types.Message):
    data = user_data[message.from_user.id]
    data["chosen_cafe"] = message.text

    await message.answer("Спасибо! Передаю твою анкету менеджеру ☕")
    await bot.send_message(
        ADMIN_ID,
        f"📋 Новая анкета\nФИО: {data['fio']}\nВозраст: {data['age']}\nТелефон: {data['phone']}\n"
        f"Город: {data['city']}\nГрафик: {data['schedule']}\nСмена: {data.get('shift', '—')}\n"
        f"Выбранная кофейня: {data['chosen_cafe']}"
    )
    log_application(data, "Принят", data["chosen_cafe"])
    user_data.pop(message.from_user.id, None)

# ---------------- FAQ ----------------

FAQ = {
    "график": "У нас есть дневные и ночные смены, полные и неполные. Расскажи, какой тебе удобнее?",
    "зарплата": "Зависит от города и формата смен. Менеджер расскажет подробнее после анкеты.",
    "возраст": "Мы принимаем кандидатов от 18 лет.",
    "форма": "Форма выдаётся на месте ☕"
}

@dp.message()
async def faq_handler(message: types.Message):
    text = message.text.lower()
    for key, answer in FAQ.items():
        if key in text:
            await message.answer(answer)
            return

# ---------------- MAIN ----------------

async def main():
    load_vacancies()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
