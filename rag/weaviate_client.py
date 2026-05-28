"""
Weaviate Cloud client + RunbookChunk collection helpers.

Mirrors the pattern from /Users/vivekanandvivek/RAG/weaviate_helper.py but
uses a project-specific collection name 'RunbookChunk' for incident-response
runbooks.

Schema:
  runbook_file     TEXT  (e.g. 'redis-memory-and-eviction.md')
  runbook_title    TEXT  (first H1 of the file)
  section_title    TEXT  (H2 of the chunk; empty for preamble)
  chunk_text       TEXT  (the actual content used at query time)
  chunk_index      INT   (position within the runbook, 0-based)
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import MetadataQuery, Filter

_COLLECTION = "RunbookChunk"
_client = None
_collection = None


def _get_client():
    global _client
    if _client is None:
        url = os.getenv("WEAVIATE_URL")
        key = os.getenv("WEAVIATE_API_KEY")
        if not url or not key:
            raise RuntimeError(
                "WEAVIATE_URL and WEAVIATE_API_KEY must be set in environment"
            )
        _client = weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=Auth.api_key(key),
        )
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        if not client.collections.exists(_COLLECTION):
            client.collections.create(
                _COLLECTION,
                properties=[
                    Property(name="runbook_file", data_type=DataType.TEXT),
                    Property(name="runbook_title", data_type=DataType.TEXT),
                    Property(name="section_title", data_type=DataType.TEXT),
                    Property(name="chunk_text", data_type=DataType.TEXT),
                    Property(name="chunk_index", data_type=DataType.INT),
                ],
            )
        _collection = client.collections.get(_COLLECTION)
    return _collection


def insert_chunk(runbook_file: str, runbook_title: str, section_title: str,
                 chunk_index: int, chunk_text: str, vector: list[float]) -> str | None:
    """Insert a chunk if not already present (dedupe by file + index)."""
    coll = _get_collection()
    existing = coll.query.fetch_objects(
        filters=(
            Filter.by_property("runbook_file").equal(runbook_file)
            & Filter.by_property("chunk_index").equal(chunk_index)
        ),
        limit=1,
    )
    if existing.objects:
        return None
    return coll.data.insert(
        properties={
            "runbook_file": runbook_file,
            "runbook_title": runbook_title,
            "section_title": section_title,
            "chunk_text": chunk_text,
            "chunk_index": chunk_index,
        },
        vector=vector,
    )


def reset_collection():
    """Delete and recreate the collection — for re-ingest."""
    global _collection
    client = _get_client()
    if client.collections.exists(_COLLECTION):
        client.collections.delete(_COLLECTION)
    _collection = None
    _get_collection()


def count_chunks() -> int:
    coll = _get_collection()
    return coll.aggregate.over_all(total_count=True).total_count


def search_near_vector(vector: list[float], limit: int = 3) -> list[dict]:
    coll = _get_collection()
    response = coll.query.near_vector(
        near_vector=vector,
        limit=limit,
        return_metadata=MetadataQuery(distance=True),
    )
    return [
        {
            "runbook_file": o.properties.get("runbook_file"),
            "runbook_title": o.properties.get("runbook_title"),
            "section_title": o.properties.get("section_title"),
            "chunk_text": o.properties.get("chunk_text"),
            "distance": o.metadata.distance,
        }
        for o in response.objects
    ]


def search_hybrid(query: str, vector: list[float], alpha: float = 0.6,
                  limit: int = 3) -> list[dict]:
    """Hybrid search: alpha=0 pure keyword (BM25), alpha=1 pure vector."""
    coll = _get_collection()
    response = coll.query.hybrid(
        query=query,
        alpha=alpha,
        vector=vector,
        limit=limit,
        return_metadata=MetadataQuery(score=True),
    )
    return [
        {
            "runbook_file": o.properties.get("runbook_file"),
            "runbook_title": o.properties.get("runbook_title"),
            "section_title": o.properties.get("section_title"),
            "chunk_text": o.properties.get("chunk_text"),
            "score": getattr(o.metadata, "score", None),
        }
        for o in response.objects
    ]


def close():
    global _client, _collection
    if _client is not None:
        _client.close()
    _client = None
    _collection = None
