import os
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select

from app.clients.database import DatabaseClient
from app.domain.auth import UserRole
from app.models.auth import User
from app.models.indexing import EmbeddingVectorCache
from app.models.project import Project
from app.repositories.indexing import IndexGenerationRepository

pytestmark = pytest.mark.postgres_integration

USER_ID = UUID(int=820_001)
PROJECT_A_ID = UUID(int=820_002)
PROJECT_B_ID = UUID(int=820_003)
CONTENT_SHA256 = "a" * 64


def _database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    return value


async def _cleanup(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        await session.execute(delete(Project).where(Project.id.in_({PROJECT_A_ID, PROJECT_B_ID})))
        await session.execute(delete(User).where(User.id == USER_ID))


async def _seed(database: DatabaseClient) -> None:
    async with database.session_scope() as session:
        session.add(
            User(
                id=USER_ID,
                email="embedding-cache@example.com",
                display_name="Embedding cache",
                password_hash="not-used",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.flush()
        session.add_all(
            [
                Project(
                    id=project_id,
                    name=name,
                    slug=slug,
                    description=None,
                    default_base_url="https://api.example.com",
                    active_server_ref=None,
                    server_mappings={},
                    mcp_hostname=f"{slug}.mcp.example.com",
                    is_enabled=True,
                    active_build_id=None,
                    active_deployment_id=None,
                    created_by=USER_ID,
                )
                for project_id, name, slug in (
                    (PROJECT_A_ID, "Embedding cache A", "embedding-cache-a"),
                    (PROJECT_B_ID, "Embedding cache B", "embedding-cache-b"),
                )
            ]
        )


async def test_embedding_cache_upsert_is_idempotent_and_project_scoped() -> None:
    database = DatabaseClient(_database_url(), pool_size=3, max_overflow=0)
    repository = IndexGenerationRepository()
    try:
        await _cleanup(database)
        await _seed(database)
        for project_id, vector in (
            (PROJECT_A_ID, [1.0, 2.0]),
            (PROJECT_B_ID, [8.0, 9.0]),
        ):
            async with database.session_scope() as session:
                await repository.upsert_cached_embeddings(
                    session,
                    project_id=project_id,
                    model_identity="embed/v1",
                    resolved_model="embed/v1:stable",
                    dimensions=2,
                    vectors_by_sha256={CONTENT_SHA256: vector},
                )

        async with database.session_scope() as session:
            project_a = await repository.list_cached_embeddings(
                session,
                project_id=PROJECT_A_ID,
                model_identity="embed/v1",
                content_sha256s=[CONTENT_SHA256],
            )
            project_b = await repository.list_cached_embeddings(
                session,
                project_id=PROJECT_B_ID,
                model_identity="embed/v1",
                content_sha256s=[CONTENT_SHA256],
            )
        assert [record.vector for record in project_a] == [[1.0, 2.0]]
        assert [record.vector for record in project_b] == [[8.0, 9.0]]

        async with database.session_scope() as session:
            await repository.upsert_cached_embeddings(
                session,
                project_id=PROJECT_A_ID,
                model_identity="embed/v1",
                resolved_model="embed/v1:replacement",
                dimensions=2,
                vectors_by_sha256={CONTENT_SHA256: [3.0, 4.0]},
            )
        async with database.session_scope() as session:
            count = await session.scalar(select(func.count(EmbeddingVectorCache.id)))
            refreshed = await repository.list_cached_embeddings(
                session,
                project_id=PROJECT_A_ID,
                model_identity="embed/v1",
                content_sha256s=[CONTENT_SHA256],
            )
        assert count == 2
        assert refreshed[0].resolved_model == "embed/v1:replacement"
        assert refreshed[0].vector == [3.0, 4.0]

        async with database.session_scope() as session:
            await session.execute(delete(Project).where(Project.id == PROJECT_A_ID))
        async with database.session_scope() as session:
            remaining = await session.scalar(select(func.count(EmbeddingVectorCache.id)))
        assert remaining == 1
    finally:
        await _cleanup(database)
        await database.close()
