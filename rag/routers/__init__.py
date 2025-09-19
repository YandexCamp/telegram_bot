from fastapi import APIRouter
from .rag_routes import router as rag

router = APIRouter(prefix="/api")
router.include_router(rag, prefix="/rag", tags=["RAG"])