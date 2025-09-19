from fastapi import APIRouter
from .telegram_bot_routers import router as telegram_bot

router = APIRouter(prefix="/api")
router.include_router(telegram_bot, prefix="/telegram_bot", tags=["telegram"])

