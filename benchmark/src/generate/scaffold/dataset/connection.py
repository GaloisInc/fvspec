"""Database connection management for pbts_full.db."""

import threading
from pathlib import Path

from sqlmodel import Session, create_engine

from generate.config import load_config

# Global engine instance (lazy initialized)
_engine = None
_engine_lock = threading.Lock()

# Connection pool multiplier: provides buffer for parallelism spikes
POOL_SIZE_MULTIPLIER = 2


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
