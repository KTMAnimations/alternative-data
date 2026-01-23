"""Pytest configuration and fixtures."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.base import Base
from src.core.config import settings


# Test database URLs (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_DATABASE_URL_SYNC = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests."""
    async_session = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
def sync_engine():
    """Create sync test engine."""
    engine = create_engine(
        TEST_DATABASE_URL_SYNC,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def sync_db_session(sync_engine) -> Generator[Session, None, None]:
    """Create sync database session for tests."""
    SessionLocal = sessionmaker(bind=sync_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest_asyncio.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database session override."""
    from src.api.main import app
    from src.core.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# Sample data fixtures
@pytest.fixture
def sample_tsa_data():
    """Sample TSA checkpoint data."""
    return [
        {
            "date": date(2024, 1, 15),
            "current_year_throughput": 2500000,
            "prior_year_throughput": 2300000,
            "yoy_change_pct": Decimal("8.6957"),
            "day_of_week": 0,
            "is_holiday_period": False,
        },
        {
            "date": date(2024, 1, 16),
            "current_year_throughput": 2600000,
            "prior_year_throughput": 2400000,
            "yoy_change_pct": Decimal("8.3333"),
            "day_of_week": 1,
            "is_holiday_period": False,
        },
    ]


@pytest.fixture
def sample_earthquake_data():
    """Sample earthquake event data."""
    return [
        {
            "event_id": "us7000abc1",
            "timestamp": datetime(2024, 1, 15, 10, 30, 0),
            "latitude": Decimal("35.6762"),
            "longitude": Decimal("139.6503"),
            "depth_km": Decimal("10.5"),
            "magnitude": Decimal("5.2"),
            "magnitude_type": "mw",
            "place_description": "10km NE of Tokyo, Japan",
            "felt_reports": 1500,
            "tsunami_flag": False,
        },
    ]


@pytest.fixture
def sample_factor_data():
    """Sample factor value data."""
    return [
        {
            "ticker": "DAL",
            "factor_id": "tsa_throughput_momentum",
            "as_of_date": date(2024, 1, 15),
            "mean": Decimal("0.0450"),
            "variance": Decimal("0.0001"),
            "data_quality": Decimal("0.95"),
        },
        {
            "ticker": "UAL",
            "factor_id": "tsa_throughput_momentum",
            "as_of_date": date(2024, 1, 15),
            "mean": Decimal("0.0380"),
            "variance": Decimal("0.0001"),
            "data_quality": Decimal("0.95"),
        },
    ]
