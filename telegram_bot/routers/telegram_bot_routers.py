from fastapi import APIRouter, HTTPException
from models.telegram_bot_models import TelegramMessage, TelegramResponse, BotStatus
import requests
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# URL для LLM агента (можно вынести в настройки)
LLM_AGENT_URL = "http://localhost:8888/api/llm_agent"


@router.post("/", response_model=TelegramResponse)
async def process_message(message: TelegramMessage):
    """
    Обрабатывает входящее сообщение от Telegram бота
    """
    try:
        logger.info(f"Получено сообщение от пользователя {message.user_id}: {message.message_text}")
        
        # Здесь будет интеграция с LLM агентом
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
        # Подготовка запроса к LLM агенту
        llm_request = {
            "headers": {
                "Authorization": "Bearer YOUR_TOKEN",  # Заменить на реальный токен
                "Content-Type": "application/json"
            },
            "payload": {
                "modelUri": "gpt://YOUR_FOLDER_ID/yandexgpt-lite",  # Заменить на реальный URI
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
