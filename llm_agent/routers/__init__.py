from fastapi import APIRouter
from .llm_agent_routers import router as llm_agent


router = APIRouter(prefix="/api")
router.include_router(llm_agent, prefix="/llm_agent", tags=["generate"])
