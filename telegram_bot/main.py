import asyncio
import uvicorn
from fastapi import FastAPI
from routers import router

app = FastAPI(
    title="Telegram Bot Microservice",
    description="Микросервис для обработки сообщений Telegram бота",
    version="1.0.0",
    debug=True
)

app.include_router(router)


@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работы сервиса"""
    return {"message": "Telegram Bot Microservice is running"}


async def main():
    """Запуск сервера"""
    uvicorn.run(
        "main:app",
        host="localhost",
        port=9999,  # Уникальный порт для Telegram бота
        reload=True,
        log_level="debug",
    )


if __name__ == "__main__":
    asyncio.run(main())
