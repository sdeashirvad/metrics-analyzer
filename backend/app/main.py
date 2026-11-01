import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, load_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.dq.router import router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    resolved = settings or load_settings()
    app = FastAPI(title="Metrics Analyzer Data Quality", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = resolved
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)

    @app.exception_handler(AppError)
    async def app_error(_request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(Exception)
    async def unexpected(_request, exc: Exception):
        logger.info("unhandled error=%s", type(exc).__name__)
        return JSONResponse(
            status_code=502,
            content={"code": "UPSTREAM_ERROR", "message": "The data service could not complete the request."},
        )

    return app


app = create_app()
