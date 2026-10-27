"""Postgres-backed jobs. The API enqueues; the worker process runs them."""

from __future__ import annotations

import logging

from procrastinate import App, PsycopgConnector, exceptions

from app.config import get_settings

logger = logging.getLogger(__name__)

procrastinate_app = App(
    connector=PsycopgConnector(conninfo=get_settings().psycopg_conninfo, min_size=1, max_size=4),
)


@procrastinate_app.task(name="run_generation", retry=0)
def run_generation(business_id: str) -> None:
    from app.services.generation import execute_generation

    execute_generation(business_id)


def enqueue_generation(business_id: str) -> None:
    try:
        run_generation.configure(lock=f"gen-{business_id}", queueing_lock=f"gen-{business_id}").defer(
            business_id=business_id
        )
    except exceptions.AlreadyEnqueued:
        logger.info("generation already queued for %s", business_id)
