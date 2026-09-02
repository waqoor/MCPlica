"""Live Milvus scale harness for 10,000 project-scoped documentation chunks."""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import statistics
import time
from typing import cast
from uuid import UUID, uuid4

from app.clients.vector import MilvusVectorClient
from app.parsers.documentation import DocumentChunk
from app.providers.milvus import MilvusVectorStore


def _vector(index: int, dimensions: int) -> list[float]:
    return [((index + 1) * (position + 3) % 101 + 1) / 102 for position in range(dimensions)]


def _chunks(
    *,
    start: int,
    count: int,
    project_id: UUID,
    generation_id: UUID,
    source_version_id: UUID,
) -> list[DocumentChunk]:
    result: list[DocumentChunk] = []
    for index in range(start, start + count):
        text = f"MCPlica Milvus benchmark documentation chunk {index}"
        content_sha256 = hashlib.sha256(text.encode()).hexdigest()
        chunk_digest = hashlib.sha256(f"{generation_id}:{index}".encode()).hexdigest()
        result.append(
            DocumentChunk(
                chunk_id=f"chunk_{chunk_digest}",
                project_id=project_id,
                generation_id=generation_id,
                source_version_id=source_version_id,
                title="Scale benchmark",
                section_path=["Scale benchmark", str(index)],
                text=text,
                content_sha256=content_sha256,
            )
        )
    return result


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return ordered[position]


async def run(
    *,
    uri: str,
    token: str | None,
    chunk_count: int,
    batch_size: int,
    dimensions: int,
    searches: int,
    collection_base: str,
) -> dict[str, object]:
    project_id = uuid4()
    generation_id = uuid4()
    source_version_id = uuid4()
    execution_token = uuid4()
    client = MilvusVectorClient(uri, token)
    store = MilvusVectorStore(client, collection_base)
    collection = store.collection_name(dimensions)
    inserted = 0
    write_attempted = False
    try:
        indexing_started = time.perf_counter()
        await store.ensure_index(collection=collection, dimensions=dimensions)
        for start in range(0, chunk_count, batch_size):
            current_count = min(batch_size, chunk_count - start)
            chunks = _chunks(
                start=start,
                count=current_count,
                project_id=project_id,
                generation_id=generation_id,
                source_version_id=source_version_id,
            )
            write_attempted = True
            await store.upsert_chunks(
                collection=collection,
                chunks=chunks,
                vectors=[
                    _vector(index, dimensions) for index in range(start, start + current_count)
                ],
                execution_token=execution_token,
            )
            inserted += current_count
        indexing_seconds = time.perf_counter() - indexing_started

        # Confirm visibility before measuring query latency. The query remains scoped by
        # both project and generation, as it is in the production retrieval path.
        visible = []
        for _attempt in range(20):
            visible = await store.search(
                collection=collection,
                project_id=project_id,
                generation_id=generation_id,
                execution_token=execution_token,
                vector=_vector(0, dimensions),
                limit=10,
            )
            if visible:
                break
            await asyncio.sleep(0.25)
        if not visible:
            raise RuntimeError("Inserted benchmark chunks did not become searchable")

        query_seconds: list[float] = []
        for index in range(searches):
            started = time.perf_counter()
            result = await store.search(
                collection=collection,
                project_id=project_id,
                generation_id=generation_id,
                execution_token=execution_token,
                vector=_vector(index % chunk_count, dimensions),
                limit=10,
            )
            query_seconds.append(time.perf_counter() - started)
            if any(item.chunk.project_id != project_id for item in result):
                raise RuntimeError("Milvus benchmark observed cross-project search results")

        return {
            "schema_version": "mcplica-milvus-benchmark/v1",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "collection": collection,
            "chunk_count": inserted,
            "dimensions": dimensions,
            "batch_size": batch_size,
            "indexing_seconds": round(indexing_seconds, 6),
            "searches": searches,
            "query_median_ms": round(statistics.median(query_seconds) * 1_000, 3),
            "query_p95_ms": round(_percentile(query_seconds, 0.95) * 1_000, 3),
        }
    finally:
        if write_attempted:
            await store.delete_generation(
                collection=collection,
                project_id=project_id,
                generation_id=generation_id,
                execution_token=execution_token,
            )
        await client.close()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", default=os.environ.get("BENCHMARK_MILVUS_URI"))
    parser.add_argument("--token", default=os.environ.get("BENCHMARK_MILVUS_TOKEN"))
    parser.add_argument("--chunks", type=int, default=10_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--dimensions", type=int, default=16)
    parser.add_argument("--searches", type=int, default=20)
    parser.add_argument("--collection-base", default="mcplica_benchmark")
    arguments = parser.parse_args()
    if not arguments.uri:
        parser.error("--uri or BENCHMARK_MILVUS_URI is required")
    for field, lower, upper in (
        ("chunks", 1, 100_000),
        ("batch_size", 1, 2_000),
        ("dimensions", 1, 4_096),
        ("searches", 1, 1_000),
    ):
        value = cast(int, getattr(arguments, field))
        if not lower <= value <= upper:
            parser.error(f"--{field.replace('_', '-')} must be between {lower} and {upper}")
    return arguments


def main() -> None:
    arguments = _arguments()
    result = asyncio.run(
        run(
            uri=cast(str, arguments.uri),
            token=cast(str | None, arguments.token),
            chunk_count=cast(int, arguments.chunks),
            batch_size=cast(int, arguments.batch_size),
            dimensions=cast(int, arguments.dimensions),
            searches=cast(int, arguments.searches),
            collection_base=cast(str, arguments.collection_base),
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
