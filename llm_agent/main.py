import asyncio
import uvicorn
from fastapi import FastAPI
from routers import router
# from settings import settings

app = FastAPI(debug=True)
app.include_router(router)


async def main():
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level="debug",
    )

if __name__ == "__main__":
    asyncio.run(main())
