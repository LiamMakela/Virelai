from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


app = FastAPI(
    title="Virelai API",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
    }


@app.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
):
    await db.execute(text("SELECT 1"))

    return {
        "status": "ready",
        "database": "ok",
    }