from pydantic import BaseModel
from typing import List, Optional


class RAGRequest(BaseModel):
    query: str
    top_k: int = 3


class DocumentResult(BaseModel):
    content: str
    source: str
    score: float
    rank: int


class RAGResult(BaseModel):
    success: bool
    context: str
    documents: List[DocumentResult] = []
    error: Optional[str] = None