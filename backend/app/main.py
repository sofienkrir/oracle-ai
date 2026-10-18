"""Point d'entrée FastAPI (monolithe modulaire).

Lancement : `uv run uvicorn app.main:create_app --factory --reload` depuis `backend/`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import datasets, system
from app.core.config import ENGINE_VERSION, Settings, get_settings
from app.core.exceptions import OracleError
from app.core.logging import configure_logging, get_logger
from app.persistence.db import Database
from app.persistence.repositories import HistoryRepository
from app.services.datasets import DatasetService

log = get_logger("api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="ORACLE AI API",
        version=ENGINE_VERSION,
        description="Intelligence décisionnelle explicable — import, qualité, analyses.",
    )
    db = Database(settings.resolved_database_url)
    db.create_all()
    repo = HistoryRepository(db)

    app.state.settings = settings
    app.state.db = db
    app.state.repo = repo
    app.state.datasets = DatasetService(settings, repo)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(OracleError)
    async def _oracle_error(_: Request, exc: OracleError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "message": "Requête invalide.",
                "details": {"errors": [str(e.get("msg")) for e in exc.errors()]},
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("erreur inattendue: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "Erreur interne inattendue. Consultez les journaux du backend.",
                "details": {},
            },
        )

    app.include_router(system.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    return app
