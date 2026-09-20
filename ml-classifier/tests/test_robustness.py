import time

import anyio


async def test_boundary_length_input_is_scored_quickly(client):
    # 32 000 characters is exactly the gateway's ChatRequest ceiling. This is
    # the shape of test that would have caught the ReDoS in the rule engine.
    started = time.perf_counter()
    resp = await client.post("/classify", json={"text": "a b " * 8000})
    elapsed = time.perf_counter() - started
    assert resp.status_code == 200
    assert elapsed < 1.0


async def test_slow_inference_does_not_block_the_event_loop(app, client):
    # Defends the anyio.to_thread decision. If predict ran on the loop, the
    # loop itself would be frozen for the full 0.5s: not just the /classify
    # call, but every timer and task on it, including the one below that
    # schedules /health. So health_elapsed is measured from a clock started
    # *before* either request is scheduled, not from inside call_health --
    # a blocked loop delays when /health can even start, and that delay is
    # invisible to a timer that only starts once /health finally runs.
    real_predict = app.state.bundle.predict
    health_elapsed = None

    def slow_predict(text):
        time.sleep(0.5)
        return real_predict(text)

    app.state.bundle.predict = slow_predict
    group_started = time.perf_counter()

    async def classify():
        await client.post("/classify", json={"text": "hello"})

    async def call_health():
        nonlocal health_elapsed
        resp = await client.get("/health")
        health_elapsed = time.perf_counter() - group_started
        assert resp.status_code == 200

    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(classify)
            await anyio.sleep(0.05)
            tg.start_soon(call_health)
    finally:
        app.state.bundle.predict = real_predict

    # /health returned well before the 0.5s sleep finished, because it ran
    # concurrently on the loop while predict slept in its worker thread. Had
    # predict run on the loop, the loop would still be blocked at the 50ms
    # mark, /health could not even start, and this would measure ~0.5s.
    assert health_elapsed is not None
    assert health_elapsed < 0.3


async def test_concurrent_requests_are_all_served(client):
    results = []

    async def one():
        resp = await client.post("/classify", json={"text": "hello there"})
        results.append(resp.status_code)

    async with anyio.create_task_group() as tg:
        for _ in range(20):
            tg.start_soon(one)

    assert results == [200] * 20
