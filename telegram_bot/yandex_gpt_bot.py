"""
Класс YandexGPTBot для работы с Telegram ботом
Этот класс будет использоваться в основном сервисе Telegram бота
"""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class YandexGPTBot:
    """
    Класс для работы с Telegram ботом и интеграции с микросервисами
    """

    def __init__(
            self,
            telegram_bot_service_url:
            str = "http://localhost:9999/api/telegram_bot"):
        """
        Инициализация бота

        Args:
            telegram_bot_service_url: URL микросервиса Telegram бота
        """
        self.telegram_bot_service_url = telegram_bot_service_url
        self.session = requests.Session()

    async def process_message(
            self,
            chat_id: int,
            user_id: int,
            message_text: str,
            username: Optional[str] = None):
        """
        Обрабатывает сообщение пользователя через микросервис

        Args:
            chat_id: ID чата
            user_id: ID пользователя
            message_text: Текст сообщения
            username: Имя пользователя (опционально)

        Returns:
            dict: Ответ от микросервиса
        """
        try:
            payload = {
                "chat_id": chat_id,
                "user_id": user_id,
                "message_text": message_text,
                "username": username
            }

            response = self.session.post(
                self.telegram_bot_service_url,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    "Ошибка микросервиса: "
                    f"{response.status_code} - {response.text}")
                return {
                    "chat_id": chat_id,
                    "response_text": "Извините, произошла ошибка "
                    "при обработке сообщения"
                    }

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка соединения с микросервисом: {str(e)}")
            return {
                "chat_id": chat_id,
                "response_text": "Извините, сервис временно недоступен"
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {str(e)}")
            return {
                "chat_id": chat_id,
                "response_text": "Извините, произошла неожиданная ошибка"
            }

    async def get_bot_status(self):
        """
        Получает статус бота

        Returns:
            dict: Статус бота
        """
        url = self.telegram_bot_service_url.replace('/api/telegram_bot', '')
        try:
            response = self.session.get(
                f"{url}/api/telegram_bot/status",
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "status": "error",
                    "message": "Не удалось получить статус"}

        except Exception as e:
            logger.error(f"Ошибка получения статуса: {str(e)}")
            return {"status": "error", "message": "Ошибка получения статуса"}
