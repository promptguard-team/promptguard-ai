import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.model import ModelBundle
from tests.paths import ARTIFACT


@pytest_asyncio.fixture
async def app():
    """The service app with the committed stub artifact loaded."""
    application = create_app()
    application.state.bundle = ModelBundle.load(ARTIFACT)
    yield application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
