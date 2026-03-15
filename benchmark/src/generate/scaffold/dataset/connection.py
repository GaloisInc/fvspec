"""Database connection management for pbts_full.db."""

import logging
import threading
from pathlib import Path

from sqlalchemy import event, text
from sqlmodel import Session, create_engine

from generate.config import load_config

logger = logging.getLogger(__name__)

# Global engine instance (lazy initialized)
_engine = None
_engine_lock = threading.Lock()

# Connection pool multiplier: provides buffer for parallelism spikes
POOL_SIZE_MULTIPLIER = 2

# Track whether indexes have been ensured for this engine
_indexes_ensured = False


def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Set SQLite performance pragmas on each new connection.

    - WAL: Better read concurrency (multiple readers, single writer)
    - synchronous=NORMAL: Safe for read-heavy workloads, ~2x faster writes
    - cache_size=-64000: ~64MB page cache (default ~8MB)
    - mmap_size=256MB: Memory-mapped I/O for faster reads
    - temp_store=MEMORY: Temp tables/indexes in RAM
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA mmap_size=268435456")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


def _ensure_indexes(engine):
    """Create secondary indexes on junction tables if they don't exist.

    The composite PKs on pbt_functions(pbt_id, function_name) and
    unit_test_functions(unit_test_id, function_name) don't cover lookups
    by function_name alone. These indexes eliminate full table scans on
    448K+ row junction tables during JOIN queries.
    """
    global _indexes_ensured
    if _indexes_ensured:
        return

    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_pbt_functions_function_name "
                "ON pbt_functions(function_name)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_unit_test_functions_function_name "
                "ON unit_test_functions(function_name)"
            )
        )
        conn.commit()
        logger.debug("Ensured secondary indexes on junction tables")

    _indexes_ensured = True


def get_engine(db_path: Path | str):
    """Get or create SQLAlchemy engine for the database.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        SQLAlchemy engine instance (cached globally)

    Note:
        Connection pool size is automatically configured based on config.meta.parallelism
        with a 1.5x multiplier for headroom. The default SQLAlchemy configuration
        (pool_size=5, max_overflow=10, total=15) is insufficient for high parallelism.

        Pool sizing:
          - Total connections = config.meta.parallelism × 1.5
          - pool_size = 1/3 of total (kept open for fast reuse)
          - max_overflow = 2/3 of total (created on demand)

        For parallelism=128: pool_size=64, max_overflow=128, total=192 connections
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            # Double-check pattern: verify _engine is still None after acquiring lock
            if _engine is None:
                db_path = Path(db_path)

                # Load config to get parallelism setting
                cfg = load_config()
                max_parallelism = int(cfg.meta.parallelism * POOL_SIZE_MULTIPLIER)

                # Split into pool_size (1/3) and max_overflow (2/3) for better performance
                # pool_size connections stay open, overflow are created/destroyed as needed
                pool_size = max_parallelism // 3
                max_overflow = max_parallelism * 2 // 3

                _engine = create_engine(
                    f"sqlite:///{db_path}",
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                    pool_timeout=30.0,
                )

                # Register SQLite performance pragmas for every connection
                event.listen(_engine, "connect", _set_sqlite_pragmas)

                # Ensure secondary indexes exist on junction tables
                _ensure_indexes(_engine)

    return _engine


def get_session(db_path: Path | str) -> Session:
    """Create a new database session.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        SQLModel Session context manager

    Usage:
        with get_session(db_path) as session:
            results = session.exec(select(Datapoint).limit(10))
    """
    return Session(get_engine(db_path))
