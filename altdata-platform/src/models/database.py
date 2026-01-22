"""Database connection and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from src.config.settings import settings

# Create engine
engine = create_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    pool_pre_ping=True,
    echo=settings.database_echo,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for models
Base = declarative_base()


def get_db_connection():
    """Get a raw database connection.
    
    Returns:
        SQLAlchemy connection object
    """
    return engine.connect()


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database sessions.
    
    Yields:
        SQLAlchemy session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions.
    
    Example:
        with get_db_session() as session:
            session.query(Entity).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> bool:
    """Check if database connection is working.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def init_db() -> None:
    """Initialize database tables.

    Creates all tables defined in models.
    """
    # Import all models to ensure they're registered
    from src.models import schemas  # noqa: F401
    from src.models import adsb  # noqa: F401
    from src.models import power_grid  # noqa: F401
    from src.models import patents  # noqa: F401
    from src.models import air_quality  # noqa: F401
    from src.models import weather  # noqa: F401
    from src.models import trends  # noqa: F401
    from src.models import sentiment  # noqa: F401
    from src.models import shipping  # noqa: F401
    from src.models import github  # noqa: F401
    from src.models import satellite  # noqa: F401
    from src.alerts import models as alert_models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all database tables.
    
    WARNING: This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)
