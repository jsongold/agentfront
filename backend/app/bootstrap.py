"""Wait for Postgres, migrate, install the job schema, seed, and ensure the media bucket."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.jobs import procrastinate_app
from app.seed import seed

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


def wait_for_database(attempts: int = 40) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"database not ready: {last_error}")


def migrate() -> None:
    ini = ROOT / "alembic.ini"
    config = Config(str(ini))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            command.upgrade(config, "head")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"migration failed: {last_error}")


def install_job_schema() -> None:
    """Apply the Procrastinate schema once. API and worker both call this."""
    procrastinate_app.open()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(8675309)"))
            try:
                exists = connection.execute(text("SELECT to_regclass('public.procrastinate_jobs')")).scalar()
                if exists is None:
                    procrastinate_app.schema_manager.apply_schema()
                    logger.info("installed procrastinate schema")
                else:
                    logger.info("procrastinate schema already present")
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(8675309)"))
                connection.commit()
    finally:
        procrastinate_app.close()


def ensure_bucket() -> None:
    settings = get_settings()
    try:
        from minio import Minio
    except Exception as exc:  # noqa: BLE001
        logger.warning("minio client unavailable: %s", exc)
        return
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    for _ in range(20):
        try:
            if not client.bucket_exists(settings.minio_bucket):
                client.make_bucket(settings.minio_bucket)
            return
        except Exception as exc:  # noqa: BLE001
            logger.info("waiting for minio: %s", exc)
            time.sleep(1)
    logger.warning("minio bucket %s was not created; image upload will fail until MinIO is up", settings.minio_bucket)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logger.info("bootstrap starting")
    wait_for_database()
    migrate()
    install_job_schema()
    ensure_bucket()
    seed()


if __name__ == "__main__":
    main()
