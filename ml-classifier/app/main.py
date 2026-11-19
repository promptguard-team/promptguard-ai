import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anyio.to_thread
from fastapi import Depends, FastAPI, HTTPException, Request, status

from app.config import Settings, get_settings
from app.metrics import INFERENCE_SECONDS, SCORE, setup_metrics
from app.model import ModelBundle, Prediction
from app.schemas import ClassifyRequest, ClassifyResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load and validate the artifact, or refuse to start."""
    settings = get_settings()
    bundle = ModelBundle.load(Path(settings.model_path))
    if bundle.is_stub:
        logger.warning(
            "Serving STUB model %s. Its verdicts are not a security control.",
            bundle.version,
        )
    app.state.bundle = bundle
    yield


def get_bundle(request: Request) -> ModelBundle:
    """Return the model loaded in the lifespan."""
    return request.app.state.bundle


def _timed_predict(bundle: ModelBundle, text: str) -> Prediction:
    """Run the model in the worker thread and time only the model itself.

    Timing here, not around run_sync, keeps thread-pool queueing out of the
    inference histogram; end-to-end latency is in the HTTP metrics.
    """
    started = time.perf_counter()
    prediction = bundle.predict(text)
    INFERENCE_SECONDS.observe(time.perf_counter() - started)
    return prediction


def create_app() -> FastAPI:
    app = FastAPI(title="PromptGuard ML Classifier", lifespan=lifespan)

    @app.post("/classify", response_model=ClassifyResponse)
    async def classify(
        body: ClassifyRequest,
        bundle: ModelBundle = Depends(get_bundle),
        settings: Settings = Depends(get_settings),
    ) -> ClassifyResponse:
        """Score one text. Returns a measurement, never a verdict."""
        if len(body.text) > settings.classifier_max_text_chars:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text too long"
            )
        prediction = await anyio.to_thread.run_sync(_timed_predict, bundle, body.text)
        SCORE.observe(prediction.score)
        return ClassifyResponse(
            label=prediction.label,
            score=prediction.score,
            model_version=bundle.version,
        )

    @app.get("/health")
    async def health(bundle: ModelBundle = Depends(get_bundle)) -> dict:
        """Readiness probe. Reports which artifact is being served."""
        return {
            "status": "ok",
            "model_version": bundle.version,
            "stub": bundle.is_stub,
        }

    setup_metrics(app)
    return app


app = create_app()
