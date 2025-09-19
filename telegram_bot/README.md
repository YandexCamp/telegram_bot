# Telegram Bot Microservice

Микросервис для обработки сообщений Telegram бота с интеграцией LLM агента.

## Структура проекта

```
telegram_bot/
├── main.py                          # Основной файл FastAPI приложения
├── models/
│   ├── __init__.py
│   └── telegram_bot_models.py       # Pydantic модели для API
├── routers/
│   ├── __init__.py
│   └── telegram_bot_routers.py     # API роутеры
├── yandex_gpt_bot.py               # Класс YandexGPTBot для интеграции
├── requirements.txt                 # Зависимости
└── README.md                       # Документация
```

## Установка и запуск

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите микросервис:
```bash
python main.py
```

Сервис будет доступен по адресу: `http://localhost:9999`

## API Endpoints

### POST /api/telegram_bot/
Обрабатывает входящее сообщение от Telegram бота.

**Запрос:**
```json
{
    "chat_id": 123456789,
    "user_id": 987654321,
    "message_text": "Привет!",
    "username": "user123"
}
```

**Ответ:**
```json
{
    "chat_id": 123456789,
    "response_text": "Привет! Как дела?",
    "parse_mode": "HTML"
}
```

### GET /api/telegram_bot/status
Возвращает статус бота.

**Ответ:**
```json
{
    "status": "active",
    "message": "Telegram Bot микросервис работает"
}
```

### GET /
Корневой эндпоинт для проверки работы сервиса.

## Интеграция с LLM Agent

Микросервис интегрирован с LLM агентом (порт 8888) для обработки сообщений пользователей.

## Использование класса YandexGPTBot

```python
from yandex_gpt_bot import YandexGPTBot

bot = YandexGPTBot("http://localhost:9999")

# Обработка сообщения
response = await bot.process_message(
    chat_id=123456789,
    user_id=987654321,
    message_text="Привет!"
)

print(response["response_text"])
```

## Порты сервисов

- Telegram Bot Microservice: 9999
- LLM Agent: 8888
- Validator: 8080
