from fastapi import APIRouter
from .validator_routes import router as validator


router = APIRouter(prefix="/api")
router.include_router(validator, prefix="/val", tags=["Validate"])
