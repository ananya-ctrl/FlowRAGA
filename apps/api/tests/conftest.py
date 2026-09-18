from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flowraga.core.config import get_settings
from flowraga.db.base import Base
from flowraga.db.dependencies import get_session
from flowraga.main import app


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    settings = get_settings()
    previous_storage_root = settings.storage_root
    settings.storage_root = str(tmp_path / "uploads")
    database_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def test_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    import asyncio

    asyncio.run(prepare_database())
    app.dependency_overrides[get_session] = test_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
    settings.storage_root = previous_storage_root
