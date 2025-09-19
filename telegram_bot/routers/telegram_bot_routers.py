from fastapi import APIRouter, HTTPException
from models.telegram_bot_models import TelegramMessage, TelegramResponse, BotStatus
import requests
import logging
import os
import time
import jwt

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# URL для LLM агента и переменные окружения
LLM_AGENT_URL = os.getenv("LLM_AGENT_URL", "http://localhost:8888/api/llm_agent")
FOLDER_ID = os.getenv("FOLDER_ID", "")
SERVICE_ACCOUNT_ID = os.getenv("SERVICE_ACCOUNT_ID", "")
KEY_ID = os.getenv("KEY_ID", "")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")


@router.post("/", response_model=TelegramResponse)
async def process_message(message: TelegramMessage):
    """
    Обрабатывает входящее сообщение от Telegram бота
    """
    try:
        logger.info(f"Получено сообщение от пользователя {message.user_id}: {message.message_text}")
        
        # Интеграция с LLM агентом
        response_text = await ask_gpt(message.message_text)
        
        return TelegramResponse(
            chat_id=message.chat_id,
            response_text=response_text
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки сообщения: {str(e)}")


@router.get("/status", response_model=BotStatus)
async def get_bot_status():
    """
    Возвращает статус бота
    """
    return BotStatus(
        status="active",
        message="Telegram Bot микросервис работает"
    )


async def ask_gpt(message_text: str) -> str:
    """
    Функция для обращения к LLM агенту
    Пока что возвращает заглушку, позже будет интегрирована с llm_agent
    """
    try:
        if not (FOLDER_ID and SERVICE_ACCOUNT_ID and KEY_ID and PRIVATE_KEY):
            logger.error("Не заданы FOLDER_ID/SERVICE_ACCOUNT_ID/KEY_ID/PRIVATE_KEY")
            return "Извините, сервис ИИ не настроен"

        # Генерация IAM токена
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': SERVICE_ACCOUNT_ID,
            'iat': now,
            'exp': now + 3600
        }
        encoded_jwt = jwt.encode(payload, PRIVATE_KEY, algorithm='PS256', headers={'kid': KEY_ID})
        iam_resp = requests.post(
            'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            json={'jwt': encoded_jwt},
            timeout=10
        )
        if iam_resp.status_code != 200:
            logger.error("Не удалось получить IAM токен: %s", iam_resp.text)
            return "Извините, сервис ИИ временно недоступен"
        iam_token = iam_resp.json().get('iamToken')

        # Подготовка запроса к LLM агенту
        llm_request = {
            "headers": {
                "Authorization": f"Bearer {iam_token}",
                "Content-Type": "application/json",
                "x-folder-id": FOLDER_ID,
            },
            "payload": {
                "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": 2000
                },
                "messages": [
                    {"role": "user", "text": message_text}
                ]
            },
            "LLM_URL": "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        }

        # Отправка запроса к LLM агенту
        response = requests.post(
            LLM_AGENT_URL,
            json=llm_request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("gen_text", "Извините, не удалось получить ответ от ИИ")
        else:
            logger.error(f"Ошибка LLM агента: {response.status_code} - {response.text}")
            return "Извините, произошла ошибка при обращении к ИИ"
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка соединения с LLM агентом: {str(e)}")
        return "Извините, сервис ИИ временно недоступен"
    except Exception as e:
        logger.error(f"Неожиданная ошибка в ask_gpt: {str(e)}")
        return "Извините, произошла неожиданная ошибка"
