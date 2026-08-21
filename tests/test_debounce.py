import asyncio

import pytest

from app.telegram.debounce import DebounceRegistry


@pytest.mark.asyncio
async def test_new_debounced_work_cancels_previous() -> None:
    registry = DebounceRegistry()
    results: list[str] = []

    async def first() -> None:
        results.append("first")

    async def second() -> None:
        results.append("second")

    registry.schedule("chat", delay_seconds=0.05, factory=first)
    registry.schedule("chat", delay_seconds=0.01, factory=second)
    await asyncio.sleep(0.08)
    await registry.shutdown()
    assert results == ["second"]
