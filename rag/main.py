import asyncio
import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from routers import router
from routers.rag import YandexRAG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

rag_system = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting RAG service...")

    global rag_system
    rag_system = YandexRAG()

    try:
        success = rag_system.initialize_rag_system()
        if success:
            logger.info("RAG system initialized successfully")
        else:
            logger.warning("RAG system initialization failed - service will start but search may not work")
    except Exception as e:
        logger.error(f"Error during RAG initialization: {e}")

    yield

    logger.info("Shutting down RAG service...")


app = FastAPI(
    title="RAG Service",
    description="RAG (Retrieval-Augmented Generation) service for document search",
    version="1.0.0",
    debug=True,
    lifespan=lifespan
)

# Подключение роутеров
app.include_router(router)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "RAG Service is running",
        "service": "rag",
        "version": "1.0.0"
    }


async def main():
    """Основная функция для запуска сервиса"""
    config = uvicorn.Config(
        "main:app",
        host="localhost",
        port=8082,
        reload=True,
        log_level="info",
    )

    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())