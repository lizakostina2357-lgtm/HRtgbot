# Coffee HR Bot с FAQ и Excel

## Состав проекта

- bot_webhook.py — код бота
- vacancies.xlsx — вакансии
- FAQ.xlsx — вопросы и ответы
- requirements.txt — зависимости

## Переменные окружения

BOT_TOKEN=8469560301:AAE8ICqpKGb07JL7X4514BNcN215UDuAqwM
WEBHOOK_URL=https://<адрес_вашего_сайта_на_Render>
PORT=8080


## Запуск на Render

1. Загрузить проект на GitHub или напрямую на Render.
2. Manual Deploy → Clear cache & deploy latest commit.
3. Бот работает через Webhook и отвечает на FAQ, а также запускает анкету на любое сообщение.

## FAQ

- Вопросы и ответы берутся из FAQ.xlsx
- Совпадение по тексту, регистр не важен.