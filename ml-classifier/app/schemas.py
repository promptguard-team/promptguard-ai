from pydantic import BaseModel, ConfigDict, Field


class ClassifyRequest(BaseModel):
    """Text submitted for injection scoring."""

    text: str = Field(min_length=1)


class ClassifyResponse(BaseModel):
    """The model's opinion. Never a verdict — the gateway owns thresholds."""

    model_config = ConfigDict(protected_namespaces=())

    label: str
    score: float
    model_version: str
