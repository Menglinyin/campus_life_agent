import asyncio
from threading import Event
import pytest
from voice.common.runner import InferenceRunner
from voice.common.errors import BusyError, WorkTimeout

def test_timeout_does_not_release_capacity_until_worker_actually_finishes():
    async def run():
        runner = InferenceRunner(1); started = Event(); finish = Event()
        def slow(): started.set(); finish.wait(timeout=2); return 'done'
        try:
            with pytest.raises(WorkTimeout): await runner.run(slow, .02)
            assert started.is_set()
            with pytest.raises(BusyError): await runner.run(lambda: 'another', .1)
        finally:
            finish.set(); await runner.close()
        assert await runner.run(lambda: 'recovered', .5) == 'recovered'
        await runner.close()
    asyncio.run(run())

def test_worker_exception_releases_capacity_and_is_reported():
    async def run():
        runner = InferenceRunner(1)
        def broken(): raise RuntimeError('synthetic error')
        with pytest.raises(RuntimeError): await runner.run(broken, .5)
        assert await runner.run(lambda: 1, .5) == 1
        await runner.close()
    asyncio.run(run())
