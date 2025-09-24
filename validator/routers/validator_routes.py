from fastapi import APIRouter, HTTPException
from models import ValidationResult, ValidationRequest
from .validator import PromptInjectionFilter


router = APIRouter()


@router.post('/', response_model=ValidationResult)
async def validate_request(req: ValidationRequest):
    user_message = req.text.lower()
    iam_token = req.iam_token
    folder_id = req.folder_id
    MODEL_NAME = f"gpt://{folder_id}/yandexgpt-lite"

    validator_model = PromptInjectionFilter(MODEL_NAME, folder_id, iam_token)

    is_insecure = validator_model.detect_llm(user_message)
    if is_insecure:
        raise HTTPException(status_code=403, detail="Toxic content detected")
    return ValidationResult(
        is_allowed=True,
    )
