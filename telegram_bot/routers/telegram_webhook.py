from fastapi import APIRouter, Request, HTTPException
from telegram import Update, Bot
from telegram.ext import Application, ContextTypes
import logging
import os
from typing import Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Telegram Bot настройки
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
TELEGRAM_SERVICE_URL = os.getenv(
    "TELEGRAM_SERVICE_URL",
    "http://localhost:9999/api/telegram_bot")

# Глобальная переменная для бота
bot: Optional[Bot] = None
application: Optional[Application] = None


def get_bot():
    """Получение экземпляра бота"""
    global bot
    if not bot and TELEGRAM_BOT_TOKEN:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return bot


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🤖 Привет! Я бот с поддержкой ИИ.\n"
        "Отправьте мне любое сообщение, и я отвечу с помощью YandexGPT!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📋 Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/status - Проверить статус бота\n"
        "\nПросто отправьте сообщение, и я отвечу!"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /status"""
    import requests
    try:
        response = requests.get(f"{TELEGRAM_SERVICE_URL}/status", timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            await update.message.reply_text(
                f"✅ Статус: {status_data['status']}\n"
                f"📝 Сообщение: {status_data['message']}"
            )
        else:
            await update.message.reply_text("❌ Ошибка получения статуса")
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        await update.message.reply_text("❌ Ошибка соединения с сервисом")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    message_text = update.message.text
    username = update.effective_user.username

    logger.info(
        f"Получено сообщение от {user_id} (@{username}): {message_text}")

    # Показываем, что бот печатает
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Отправляем запрос к микросервису обработки сообщений
        import requests

        message_data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "message_text": message_text,
            "username": username
        }

        response = requests.post(
            f"{TELEGRAM_SERVICE_URL}/",
            json=message_data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            await update.message.reply_text(
                result["response_text"],
                parse_mode=result.get("parse_mode", "HTML")
            )
        else:
            logger.error(f"Ошибка микросервиса: {response.status_code}")
            await update.message.reply_text("❌ Ошибка обработки сообщения")

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка соединения с микросервисом: {e}")
        await update.message.reply_text("❌ Ошибка соединения с сервисом")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        await update.message.reply_text("❌ Произошла внутренняя ошибка")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке сообщения"
        )


@router.post("/webhook")
async def webhook(request: Request):
    """Webhook для получения обновлений от Telegram"""
    try:
        data = await request.json()
        update = Update.de_json(data, get_bot())

        if update:
            # Обрабатываем обновление
            if update.message:
                if update.message.text:
                    if update.message.text.startswith('/'):
                        # Обработка команд
                        if update.message.text.startswith('/start'):
                            await start_command(update, None)
                        elif update.message.text.startswith('/help'):
                            await help_command(update, None)
                        elif update.message.text.startswith('/status'):
                            await status_command(update, None)
                    else:
                        # Обработка обычных сообщений
                        await handle_message(update, None)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Ошибка в webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/set-webhook")
async def set_webhook():
    """Установка webhook для Telegram бота"""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="TELEGRAM_BOT_TOKEN not set")

    if not WEBHOOK_URL:
        raise HTTPException(status_code=500, detail="WEBHOOK_URL not set")

    try:
        bot = get_bot()
        webhook_url = f"{WEBHOOK_URL}/api/telegram_bot/webhook"

        result = await bot.set_webhook(url=webhook_url)

        if result:
            return {
                "status": "success",
                "message": f"Webhook установлен: {webhook_url}",
                "webhook_url": webhook_url
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to set webhook")

    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error setting webhook: {
                str(e)}")


@router.get("/delete-webhook")
async def delete_webhook():
    """Удаление webhook для Telegram бота"""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="TELEGRAM_BOT_TOKEN not set")

    try:
        bot = get_bot()
        result = await bot.delete_webhook()

        if result:
            return {
                "status": "success",
                "message": "Webhook удален"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete webhook")

    except Exception as e:
        logger.error(f"Ошибка удаления webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting webhook: {
                str(e)}")


@router.get("/webhook-info")
async def get_webhook_info():
    """Получение информации о webhook"""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="TELEGRAM_BOT_TOKEN not set")

    try:
        bot = get_bot()
        webhook_info = await bot.get_webhook_info()

        return {
            "status": "success",
            "webhook_info": {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": webhook_info.last_error_date,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates
            }
        }

    except Exception as e:
        logger.error(f"Ошибка получения информации о webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting webhook info: {
                str(e)}")
