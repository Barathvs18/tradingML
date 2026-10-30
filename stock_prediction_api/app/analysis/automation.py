"""Polling worker for paper strategy schedules and in-app alerts."""

import asyncio
import logging

from app.analysis.store import get_store

logger = logging.getLogger(__name__)


async def run_automation_worker():
    while True:
        try:
            await asyncio.to_thread(get_store().automation_tick)
        except Exception:
            logger.exception("Paper strategy scheduler iteration failed")
        await asyncio.sleep(30)
