from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Hashable

logger = logging.getLogger(__name__)


class DebounceRegistry:
    """Per-chat debounce for bursts of Telegram messages.

    New work for the same key cancels the older pending/running task. Database revision guards
    remain the durable second line of defense, so cancellation is only an optimization.
    """

    def __init__(self) -> None:
        self._tasks: dict[Hashable, asyncio.Task[None]] = {}

    def schedule(
        self,
        key: Hashable,
        *,
        delay_seconds: float,
        factory: Callable[[], Awaitable[None]],
    ) -> asyncio.Task[None]:
        previous = self._tasks.get(key)
        if previous and not previous.done():
            previous.cancel()

        async def runner() -> None:
            try:
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                await factory()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("debounced_task_failed key=%r", key)
            finally:
                current = self._tasks.get(key)
                if current is asyncio.current_task():
                    self._tasks.pop(key, None)

        task = asyncio.create_task(runner(), name=f"secretary-debounce-{key}")
        self._tasks[key] = task
        return task

    def cancel(self, key: Hashable) -> None:
        task = self._tasks.pop(key, None)
        if task and not task.done():
            task.cancel()

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
