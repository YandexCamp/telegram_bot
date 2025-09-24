from fastapi import APIRouter
from models.telegram_bot_models import (
    TelegramMessage,
    TelegramResponse,
    BotStatus
)
import requests
import logging
import os
import time
import jwt
from prompt_injection import PromptInjectionFilter

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# URL микросервиса LLM Agent
LLM_AGENT_URL = os.getenv(
    "LLM_AGENT_URL",
    "http://localhost:8888/api/llm_agent")

# Yandex Cloud настройки
FOLDER_ID = os.getenv("FOLDER_ID", "")
SERVICE_ACCOUNT_ID = os.getenv("SERVICE_ACCOUNT_ID", "")
KEY_ID = os.getenv("KEY_ID", "")
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
LLM_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Кэш для IAM токена
_iam_token_cache = {"token": None, "expires": 0}


def get_iam_token():
    """Получение IAM токена для Yandex Cloud"""
    current_time = time.time()

    # Проверяем, не истек ли токен
    if (
        _iam_token_cache["token"]
        and current_time < _iam_token_cache["expires"]
    ):
        return _iam_token_cache["token"]

    try:
        # Создаем JWT токен
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': SERVICE_ACCOUNT_ID,
            'iat': now,
            'exp': now + 3600
        }

        # Создаем JWT
        encoded_token = jwt.encode(
            payload,
            PRIVATE_KEY,
            algorithm='PS256',
            headers={'kid': KEY_ID}
        )

        # Получаем IAM токен
        response = requests.post(
            'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            json={'jwt': encoded_token},
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code == 200:
            iam_token = response.json()['iamToken']
            _iam_token_cache["token"] = iam_token
            _iam_token_cache["expires"] = current_time + 3300  # 55 минут
            logger.info("IAM токен успешно получен")
            return iam_token
        else:
            logger.error(
                "Ошибка получения IAM токена: "
                f"{response.status_code} - {response.text}"
            )
            return None

    except Exception as e:
        logger.error(f"Ошибка при получении IAM токена: {e}")
        return None


@router.post("/", response_model=TelegramResponse)
async def process_message(message: TelegramMessage):
    """Обработка сообщения от Telegram бота"""
    try:
        logger.info(
            f"Получено сообщение от пользователя {
                message.user_id}: {
                message.message_text}")

        # Проверяем наличие необходимых переменных окружения
        if not all([FOLDER_ID, SERVICE_ACCOUNT_ID, KEY_ID, PRIVATE_KEY]):
            logger.error(
                "Не все переменные окружения для Yandex Cloud настроены")
            return TelegramResponse(
                chat_id=message.chat_id,
                response_text="❌ Ошибка конфигурации сервиса"
            )

        # Проверка на prompt injection
        injection_filter = PromptInjectionFilter(
            f"gpt://{FOLDER_ID}/yandexgpt-lite",
            folder_id=FOLDER_ID,
            token_getter=lambda: get_iam_token()
        )

        if injection_filter.detect_llm(message.message_text):
            logger.warning(
                "Обнаружена попытка prompt injection "
                f"от пользователя {message.user_id}"
            )
            return TelegramResponse(
                chat_id=message.chat_id,
                response_text="⚠️ Обнаружена попытка несанкционированного "
                "доступа. Сообщение заблокировано."
            )

        # Получаем ответ от LLM
        response_text = await ask_gpt(message.message_text)

        return TelegramResponse(
            chat_id=message.chat_id,
            response_text=response_text
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        return TelegramResponse(
            chat_id=message.chat_id,
            response_text="❌ Произошла ошибка при обработке вашего сообщения"
        )


@router.get("/status", response_model=BotStatus)
async def get_bot_status():
    """Получение статуса бота"""
    return BotStatus(
        status="running",
        message="Telegram Bot микросервис работает"
    )


async def ask_gpt(message_text: str) -> str:
    """Запрос к LLM через микросервис LLM Agent"""
    try:
        # Получаем IAM токен
        iam_token = get_iam_token()
        if not iam_token:
            return "❌ Ошибка аутентификации с Yandex Cloud"

        # Формируем запрос к LLM Agent
        llm_request = {
            "headers": {
                "Authorization": f"Bearer {iam_token}",
                "Content-Type": "application/json"
            },
            "payload": {
                "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": 2000
                },
                "messages": [
                    {
                        "role": "user",
                        "text": message_text
                    }
                ]
            },
            "LLM_URL": LLM_URL
        }

        # Отправляем запрос к LLM Agent
        response = requests.post(LLM_AGENT_URL, json=llm_request, timeout=30)

        if response.status_code == 200:
            result = response.json()
            return result.get("result", "❌ Пустой ответ от ИИ")
        else:
            logger.error(
                f"Ошибка LLM Agent: {response.status_code} - {response.text}")
            return "❌ Ошибка при обращении к ИИ"

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка соединения с LLM Agent: {e}")
        return "❌ Ошибка соединения с сервисом ИИ"
    except Exception as e:
        logger.error(f"Неожиданная ошибка в ask_gpt: {e}")
        return "❌ Внутренняя ошибка сервиса"
