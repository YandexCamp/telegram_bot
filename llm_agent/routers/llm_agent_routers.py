from fastapi import APIRouter
from models import LLMResult, LLMRequest
import requests
import logging

logger = logging.getLogger(__name__)


router = APIRouter()


@router.post('/', response_model=LLMResult)
async def validate_request(req: LLMRequest):
    headers = req.headers
    payload = req.payload
    LLM_URL = req.LLM_URL

    response = requests.post(
        LLM_URL,
        headers=headers,
        json=payload,
        timeout=15
    )

    if response.status_code != 200:
        logger.error(f"Yandex GPT API error: {response.text}")
        raise Exception(f"Ошибка API: {response.status_code}")

    gen_text = response.json()['result']['alternatives'][0]['message']['text']

    return LLMResult(
        gen_text=gen_text,
    )
