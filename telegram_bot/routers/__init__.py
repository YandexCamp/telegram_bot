from fastapi import APIRouter
from .telegram_bot_routers import router as telegram_bot
from .telegram_webhook import router as telegram_webhook

router = APIRouter(prefix="/api")
router.include_router(telegram_bot, prefix="/telegram_bot", tags=["telegram"])
router.include_router(telegram_webhook, prefix="/telegram_bot", tags=["webhook"])


