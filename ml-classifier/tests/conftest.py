import anyio
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.model import ModelBundle
from tests.tiny_model import build_tiny_model, write_card


@pytest.fixture(scope="session")
def tiny_model(tmp_path_factory):
    """(card_path, model_dir) of a tiny random model, built once per run."""
    root = tmp_path_factory.mktemp("tiny")
    model_dir = root / "model"
    build_tiny_model(model_dir)
    return write_card(model_dir, root / "model.card.json"), model_dir


@pytest.fixture(scope="session")
def bundle(tiny_model):
    card_path, model_dir = tiny_model
    return ModelBundle.load(card_path, model_dir, max_windows=8)


@pytest_asyncio.fixture
async def app(bundle):
    """The service app with the tiny model loaded and a single-slot limiter."""
    application = create_app()
    application.state.bundle = bundle
    application.state.limiter = anyio.CapacityLimiter(1)
    yield application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
