from typing import Dict
from pydantic import BaseModel, JsonValue, HttpUrl


class LLMRequest(BaseModel):
    headers: Dict[str, str]
    payload: Dict[str, JsonValue]
    LLM_URL: str | HttpUrl


class LLMResult(BaseModel):
    gen_text: str
