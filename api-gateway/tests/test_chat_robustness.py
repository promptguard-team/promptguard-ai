import asyncio
import time

import anyio
import httpx

from app.classifier import ClassifierClient
from app.models import MLStatus
from tests.helpers import audit_events, override_classifier, override_llm, scoring


async def test_maximum_length_prompt_completes_promptly(app, client, auth_headers):
    # 32 000 characters is exactly ChatRequest's ceiling. "sk-" followed by
    # hyphenated filler is the shape that made the OpenAI-key rule backtrack
    # quadratically and freeze the event loop for seconds. A linear scan takes
    # milliseconds, so the generous bound only trips on a real regression.
    prompt = ("sk-" + "a-" * 16000)[:32000]
    assert len(prompt) == 32000
    started = time.perf_counter()
    resp = await client.post("/chat", json={"prompt": prompt}, headers=auth_headers)
    elapsed = time.perf_counter() - started
    assert resp.status_code in {200, 403}
    assert elapsed < 2.0


async def test_concurrent_chats_are_not_starved(app, client, auth_headers):
    override_classifier(app, scoring(0.05, label="clean"))
    requests = 10
    provider_delay = 0.5

    async def slow_llm(request: httpx.Request) -> httpx.Response:
        await anyio.sleep(provider_delay)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "mock reply"}}]}
        )

    override_llm(app, slow_llm)
    codes = []

    async def one():
        resp = await client.post(
            "/chat", json={"prompt": "hello there"}, headers=auth_headers
        )
        codes.append(resp.status_code)

    started = time.perf_counter()
    async with anyio.create_task_group() as tg:
        for _ in range(requests):
            tg.start_soon(one)
    elapsed = time.perf_counter() - started

    assert codes == [200] * requests
    # Overlapped, the requests cost about one provider delay (0.5s) plus
    # overhead; run one after another they cost at least 10 * 0.5 = 5s. The
    # bound sits far from both, so it fails only if the requests serialize
    # (a blocked event loop, or a lock/session/connection held across the
    # provider call) and not on a merely slow runner.
    assert elapsed < 2.5


async def test_slow_classifier_does_not_exceed_its_timeout_budget(
    app, client, auth_headers
):
    # httpx.MockTransport never enforces timeouts, so a mocked slow handler
    # would complete and prove nothing. A real socket server that answers
    # after 1.0s makes the 0.2s timeout the only thing that can cut it short.
    answer_delay = 1.0
    body = b'{"label": "clean", "score": 0.0, "model_version": "x"}'

    handlers: set[asyncio.Task] = set()

    async def slow_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        handlers.add(asyncio.current_task())
        await reader.read(65536)
        await asyncio.sleep(answer_delay)
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        try:
            await writer.drain()
        except ConnectionError:
            pass
        writer.close()

    server = await asyncio.start_server(slow_server, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        await app.state.classifier_client.aclose()
        app.state.classifier_client = ClassifierClient(
            base_url=f"http://127.0.0.1:{port}", timeout_seconds=0.2
        )
        started = time.perf_counter()
        resp = await client.post("/chat", json={"prompt": "hi"}, headers=auth_headers)
        elapsed = time.perf_counter() - started
    finally:
        await app.state.classifier_client.aclose()
        server.close()
        for task in handlers:
            task.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)
        await server.wait_closed()

    # A refused or proxied connection would also return fast with `unavailable`,
    # so prove the request actually reached the server and the timeout fired.
    assert handlers
    # The timeout fires at 0.2s; an ignored timeout would wait the full 1.0s.
    assert elapsed < answer_delay * 0.75
    assert resp.status_code == 200
    events = await audit_events(app)
    assert len(events) == 1
    assert events[0].ml_status == MLStatus.unavailable
