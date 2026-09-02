"""Exercise real Milvus row identity with the canonical store in disposable Compose."""

import asyncio
import os
from uuid import UUID, uuid4

from app.clients.vector import MilvusVectorClient
from app.core.config import Settings
from app.parsers.documentation import (
    DocumentChunk,
    DocumentSection,
    NormalizedDocument,
    chunk_document,
)
from app.parsers.openapi.parser import parse_openapi
from app.providers.milvus import MilvusVectorStore
from app.services.indexing.service import semantic_chunks


async def main() -> None:
    settings = Settings()
    if settings.is_production or os.getenv("RUN_DOCKER_INTEGRATION") != "1":
        raise RuntimeError("Vector acceptance requires an explicitly disposable installation")
    client = MilvusVectorClient(settings.milvus_uri)
    store = MilvusVectorStore(client, f"acceptance_{uuid4().hex}")
    collection = store.collection_name(2)
    project_a, project_b, generation_a, generation_b, source_id = (uuid4() for _ in range(5))
    scopes = [(project_a, generation_a), (project_a, generation_b), (project_b, generation_a)]
    expected: dict[tuple[UUID, UUID], set[str]] = {}
    execution_tokens = {scope: uuid4() for scope in scopes}
    chunks_by_scope: dict[tuple[UUID, UUID], list[DocumentChunk]] = {}
    try:
        await store.ensure_index(collection=collection, dimensions=2)
        for project, generation in scopes:
            document = NormalizedDocument(
                source_version_id=source_id,
                title="Shared guide",
                text="Identical documentation",
                sections=[
                    DocumentSection(path=["Guide"], text="Identical documentation", ordinal=0)
                ],
            )
            chunks = chunk_document(
                document,
                project_id=project,
                generation_id=generation,
                source_content_sha256="a" * 64,
                max_chars=500,
                overlap_chars=0,
            )
            canonical = parse_openapi(
                {
                    "openapi": "3.1.0",
                    "info": {"title": "Shared API", "version": "1"},
                    "servers": [{"url": "https://api.example.com"}],
                    "paths": {"/items": {"get": {"responses": {"200": {"description": "OK"}}}}},
                },
                project_id=project,
                source_version_id=source_id,
                content_sha256="a" * 64,
            )
            chunks.extend(
                semantic_chunks(
                    canonical,
                    project_id=project,
                    generation_id=generation,
                    max_chars=6000,
                )
            )
            expected[(project, generation)] = {chunk.chunk_id for chunk in chunks}
            chunks_by_scope[(project, generation)] = chunks
            for _ in range(2):
                await store.upsert_chunks(
                    collection=collection,
                    chunks=chunks,
                    vectors=[[1.0, 0.0]] * len(chunks),
                    execution_token=execution_tokens[(project, generation)],
                )
        for project, generation in scopes:
            matches = await store.search(
                collection=collection,
                project_id=project,
                generation_id=generation,
                execution_token=execution_tokens[(project, generation)],
                vector=[1.0, 0.0],
                limit=100,
            )
            assert {match.chunk.chunk_id for match in matches} == expected[(project, generation)]

        # A reclaimed Build may publish the same canonical chunks under a new token.
        # Cleaning the obsolete attempt must preserve the replacement rows.
        first_scope = scopes[0]
        replacement_token = uuid4()
        replacement_chunks = chunks_by_scope[first_scope]
        await store.upsert_chunks(
            collection=collection,
            chunks=replacement_chunks,
            vectors=[[1.0, 0.0]] * len(replacement_chunks),
            execution_token=replacement_token,
        )
        await store.delete_generation(
            collection=collection,
            project_id=project_a,
            generation_id=generation_a,
            execution_token=execution_tokens[first_scope],
        )
        stale_matches = await store.search(
            collection=collection,
            project_id=project_a,
            generation_id=generation_a,
            execution_token=execution_tokens[first_scope],
            vector=[1.0, 0.0],
            limit=100,
        )
        replacement_matches = await store.search(
            collection=collection,
            project_id=project_a,
            generation_id=generation_a,
            execution_token=replacement_token,
            vector=[1.0, 0.0],
            limit=100,
        )
        assert stale_matches == []
        assert {match.chunk.chunk_id for match in replacement_matches} == expected[first_scope]

        await store.delete_generation(
            collection=collection, project_id=project_a, generation_id=generation_a
        )
        for project, generation in scopes:
            matches = await store.search(
                collection=collection,
                project_id=project,
                generation_id=generation,
                execution_token=(
                    replacement_token
                    if (project, generation) == first_scope
                    else execution_tokens[(project, generation)]
                ),
                vector=[1.0, 0.0],
                limit=100,
            )
            wanted: set[str] = (
                set() if (project, generation) == scopes[0] else expected[(project, generation)]
            )
            assert {match.chunk.chunk_id for match in matches} == wanted
        print(
            "Real Milvus: project/generation/attempt isolation, repeat upsert, and scoped cleanup "
            "passed."
        )
    finally:
        try:
            for project, generation in scopes:
                await store.delete_generation(
                    collection=collection, project_id=project, generation_id=generation
                )
        finally:
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
