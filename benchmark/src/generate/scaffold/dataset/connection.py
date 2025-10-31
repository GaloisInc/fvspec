"""Database connection management for pbts_full.db."""

from pathlib import Path

from sqlmodel import Session, create_engine

# Global engine instance (lazy initialized)
_engine = None


def get_engine(db_path: Path | str):
    """Get or create SQLAlchemy engine for the database.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        SQLAlchemy engine instance (cached globally)
    """
    global _engine
    if _engine is None:
        db_path = Path(db_path)
        _engine = create_engine(f"sqlite:///{db_path}")
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
