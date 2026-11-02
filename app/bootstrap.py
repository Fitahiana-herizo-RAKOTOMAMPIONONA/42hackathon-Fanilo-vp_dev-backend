from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.infrastructure.database.database import engine
from app.modules.auth.router import auth_router
from app.modules.editorial.router import editorial_router
from app.modules.news.router import news_router
from app.modules.verification.router import verification_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # Permettre les requêtes cross-origin depuis n'importe quel frontend/navigateur
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        auth_router,
        prefix="/api/v1",
    )

    app.include_router(
        news_router,
        prefix="/api/v1",
    )

    app.include_router(
        verification_router,
        prefix="/api/v1",
    )

    app.include_router(
        editorial_router,
        prefix="/api/v1",
    )

    return app