from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .admin_routes import router as admin_router
from .api import router
from .config import settings
from .database import initialize_database
from .seed import seed_demo_data
from .student_routes import router as student_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(database_path: Path | None = None) -> FastAPI:
    selected_database = database_path or settings.database_path

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if not _app.state.session_secret or len(_app.state.session_secret) < 32:
            raise RuntimeError(
                "SESSION_SECRET must be configured with at least 32 characters before starting the API."
            )
        initialize_database(selected_database)
        seed_demo_data(selected_database)
        yield

    application = FastAPI(
        title="Skillonex Academy API",
        version="0.1.0",
        description="Foundation API for the AI Student Task Management System.",
        lifespan=lifespan,
    )
    application.state.database_path = selected_database
    application.state.session_secret = settings.session_secret
    application.state.cookie_secure = settings.cookie_secure
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    application.include_router(router)
    application.include_router(admin_router)
    application.include_router(student_router)
    return application


app = create_app()
