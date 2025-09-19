from pydantic import BaseModel
from typing import Optional


class TelegramMessage(BaseModel):
    """Модель для входящего сообщения от Telegram бота"""
    chat_id: int
    user_id: int
    message_text: str
    username: Optional[str] = None


class TelegramResponse(BaseModel):
    """Модель для ответа Telegram боту"""
    chat_id: int
    response_text: str
    parse_mode: Optional[str] = "HTML"


class BotStatus(BaseModel):
    """Модель для статуса бота"""
    status: str
    message: str

