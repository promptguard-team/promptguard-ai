from dataclasses import dataclass

import anyio
import httpx

from app.models.audit import MAX_ML_LABEL_CHARS, MAX_ML_MODEL_VERSION_CHARS


class ClassifierError(Exception):
    """The classifier service could not produce a usable verdict."""


@dataclass(frozen=True)
class Verdict:
    """What the model said. Not a decision — the gateway owns thresholds."""

    label: str
    score: float
    model_version: str


class ClassifierClient:
    """Client for the ml-classifier service."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport
        )

    async def classify(self, text: str) -> Verdict:
        """Score one text, or raise ClassifierError."""
        # httpx's read timeout is the gap between reads, not elapsed time, so a
        # classifier dribbling one byte at a time would hold /chat open for as
        # long as it liked. The timeout is a budget for the whole call.
        try:
            with anyio.fail_after(self._timeout_seconds):
                response = await self._client.post("/classify", json={"text": text})
                response.raise_for_status()
        except TimeoutError as exc:
            raise ClassifierError(
                f"classifier exceeded its {self._timeout_seconds}s budget"
            ) from exc
        except httpx.HTTPError as exc:
            raise ClassifierError(str(exc)) from exc

        try:
            data = response.json()
            label = data["label"]
            score = data["score"]
            version = data["model_version"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ClassifierError("malformed classifier response") from exc

        if not isinstance(label, str) or not isinstance(version, str):
            raise ClassifierError("malformed classifier response")
        # A delivered model's classes_ and card are outside our control, and
        # these two land in fixed-width audit columns. Reject them here, where
        # the fail-open path still catches it, rather than in the INSERT that
        # follows the provider call.
        if len(label) > MAX_ML_LABEL_CHARS:
            raise ClassifierError(
                f"label is {len(label)} characters; the limit is {MAX_ML_LABEL_CHARS}"
            )
        if len(version) > MAX_ML_MODEL_VERSION_CHARS:
            raise ClassifierError(
                f"model_version is {len(version)} characters; "
                f"the limit is {MAX_ML_MODEL_VERSION_CHARS}"
            )
        # bool is a subclass of int, so True would otherwise pass as 1.0.
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ClassifierError("malformed classifier response")
        if not 0.0 <= score <= 1.0:
            raise ClassifierError(f"score out of range: {score}")

        return Verdict(label=label, score=float(score), model_version=version)

    async def aclose(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()
