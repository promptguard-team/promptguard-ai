from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import build_engine, build_sessionmaker
from app.llm import LLMClient
from app.models import Base
from app.routers import auth, chat, health

_SENSITIVE_FIELDS = frozenset({"password", "prompt"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the engine and create tables on startup, dispose on shutdown."""
    settings = get_settings()
    engine = build_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)
    app.state.llm_client = LLMClient(
        api_base=settings.llm_api_base,
        api_key=settings.openai_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    try:
        yield
    finally:
        try:
            await app.state.llm_client.aclose()
        finally:
            await engine.dispose()


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation errors with submitted secrets redacted.

    Auth routes drop `input` from every error outright: a non-object body
    (e.g. a JSON array) collapses `loc` to just ["body"], so the field-name
    check below would otherwise echo the whole payload, password included.
    """
    redact_all_input = request.url.path.startswith("/auth")
    errors = []
    for error in exc.errors():
        if redact_all_input:
            error = {k: v for k, v in error.items() if k != "input"}
        elif _SENSITIVE_FIELDS.intersection(str(part) for part in error.get("loc", ())):
            error = {**error, "input": "[redacted]"}
        errors.append(error)
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


def create_app() -> FastAPI:
    app = FastAPI(title="PromptGuard API Gateway", lifespan=lifespan)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    return app


app = create_app()
