import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import anyio.to_thread
import torch
from fastapi import Depends, FastAPI, HTTPException, Request, status

from app.config import Settings, get_settings
from app.model import ModelBundle
from app.schemas import ClassifyRequest, ClassifyResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and validate the model, or refuse to start."""
    settings = get_settings()
    if settings.classifier_torch_threads is not None:
        # Must run before any inference (including the load's warm-up): torch's
        # worker threads pick up the global thread count lazily, on first use.
        torch.set_num_threads(settings.classifier_torch_threads)
    bundle = ModelBundle.load(
        Path(settings.model_card_path),
        Path(settings.model_dir),
        settings.classifier_max_windows,
    )
    if bundle.is_stub:
        logger.warning(
            "Serving STUB model %s. Its verdicts are not a security control.",
            bundle.version,
        )
    logger.info("Serving model %s", bundle.version)
    app.state.bundle = bundle
    # One limiter for all requests: extra inferences queue rather than split
    # the CPU, which would make every request miss the gateway's budget.
    app.state.limiter = anyio.CapacityLimiter(settings.classifier_max_concurrency)
    yield


def get_bundle(request: Request) -> ModelBundle:
    """Return the model loaded in the lifespan."""
    return request.app.state.bundle


def get_limiter(request: Request) -> anyio.CapacityLimiter:
    """Return the inference limiter created in the lifespan."""
    return request.app.state.limiter


def create_app() -> FastAPI:
    app = FastAPI(title="PromptGuard ML Classifier", lifespan=lifespan)

    @app.post("/classify", response_model=ClassifyResponse)
    async def classify(
        body: ClassifyRequest,
        bundle: ModelBundle = Depends(get_bundle),
        limiter: anyio.CapacityLimiter = Depends(get_limiter),
        settings: Settings = Depends(get_settings),
    ) -> ClassifyResponse:
        """Score one text. Returns a measurement, never a verdict."""
        if len(body.text) > settings.classifier_max_text_chars:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text too long"
            )
        prediction = None
        # The deadline cancels the wait for a limiter slot promptly. A thread
        # that already runs cannot be cancelled: that inference completes, and
        # its result is still returned even if the deadline passed meanwhile.
        with anyio.move_on_after(settings.classifier_queue_timeout_seconds):
            prediction = await anyio.to_thread.run_sync(
                bundle.predict, body.text, limiter=limiter
            )
        if prediction is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, detail="classifier busy"
            )
        return ClassifyResponse(
            label=prediction.label,
            score=prediction.score,
            model_version=bundle.version,
        )

    @app.get("/health")
    async def health(bundle: ModelBundle = Depends(get_bundle)) -> dict:
        """Readiness probe. Reports which model is being served."""
        return {
            "status": "ok",
            "model_version": bundle.version,
            "stub": bundle.is_stub,
        }

    return app


app = create_app()
