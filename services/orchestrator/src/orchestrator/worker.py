"""Temporal worker entrypoint for orchestrator workflows and activities."""
from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from orchestrator.client import get_temporal_client
from orchestrator.config import get_settings
from orchestrator.registry import ALL_ACTIVITIES, ALL_WORKFLOWS


async def run_worker() -> None:
    """Run the fully registered worker on the configured task queue."""
    settings = get_settings()
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
    )
    await worker.run()


def main() -> None:
    """Run the worker process."""
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
