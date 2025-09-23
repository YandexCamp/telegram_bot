import asyncio
import uvicorn
from fastapi import FastAPI
from routers import router
from bot_app import start_bot_in_background
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Telegram Bot Service",
    description="Основной сервис Telegram бота с поддержкой ИИ",
    version="1.0.0",
    debug=True
)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("🚀 Telegram Bot Service запущен")
    start_bot_in_background()
    logger.info("📋 Доступные эндпоинты:")
    logger.info("  • POST /api/telegram_bot/ - Обработка сообщений")
    logger.info("  • GET /api/telegram_bot/status - Статус бота")
    logger.info("  • POST /api/telegram_bot/webhook - Webhook для Telegram")
    logger.info("  • GET /api/telegram_bot/set-webhook - Установка webhook")
    logger.info("  • GET /api/telegram_bot/delete-webhook - Удаление webhook")
    logger.info("  • GET /api/telegram_bot/webhook-info - Информация о webhook")

@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке"""
    logger.info("🛑 Telegram Bot Service остановлен")



async def main():
    uvicorn.run(
        "main:app",
        host="localhost",
        port=9999,  # Port for Telegram Bot
        reload=True,
        log_level="debug",
    )


if __name__ == "__main__":
    asyncio.run(main())
