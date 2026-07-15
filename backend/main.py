from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.assistant import router as assistant_router
from app.api.recall import router as recall_router
from app.api.recall_output import router as recall_output_router
from app.api.sessions import router as sessions_router
from app.api.speech import router as speech_router
from app.api.realtime import router as realtime_router
from app.core.config import settings
from app.db.database import SessionLocal
from app.db.init_db import initialize_database
from app.services.webex_auto_agent import webex_auto_agent_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(sessions_router)
app.include_router(assistant_router)
app.include_router(speech_router)
app.include_router(recall_router)
app.include_router(recall_output_router)
app.include_router(realtime_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} API is running",
        "health": "/api/health",
        "documentation": "/docs",
    }


@app.get("/api/health")
def health_check() -> dict:
    database_status = "unavailable"

    try:
        with SessionLocal() as database:
            database.execute(text("SELECT 1"))

        database_status = "connected"

    except Exception as error:
        database_status = f"error: {error}"

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "0.5.0",
        "database": database_status,
        "openai_configured": bool(
            settings.openai_api_key
        ),
        "recall_configured": bool(
            settings.recall_api_key
        ),
        "text_model": settings.openai_text_model,
        "tts_model": settings.openai_tts_model,
        "tts_voice": settings.openai_tts_voice,
    }


@app.on_event("startup")
async def start_webex_auto_agent():
    import asyncio

    asyncio.create_task(webex_auto_agent_loop())

