from pydantic import BaseModel


class ValidationRequest(BaseModel):
    text: str
    folder_id: str
    iam_token: str


class ValidationResult(BaseModel):
    is_allowed: bool
