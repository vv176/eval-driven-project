"""
Shared Weaviate helpers for the RAG technique demos.

All demos retrieve from Weaviate (same backend as the hybrid + AskCorp demos).
This module is a thin wrapper: create a collection, ingest docs (bring-your-own
OpenAI vectors), and run a vector (nearest-neighbor) search. Weaviate does the
similarity computation and ranking — so there is no in-memory cosine here.

What remains here vs. what Weaviate replaced:
  - get_embedding / get_embeddings : still needed (we embed docs to ingest, and
    embed the query / HyDE hypothetical answer to search with).
  - ingest_collection / vector_search : the Weaviate operations.
  - rank_of : a tiny helper to locate the target doc's position in the ranked
    results, used only to print each demo's "naive vs technique" verdict.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import MetadataQuery

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from rag.embedder import get_embedding, get_embeddings  # noqa: E402  (re-exported)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = weaviate.connect_to_weaviate_cloud(
            cluster_url=os.getenv("WEAVIATE_URL"),
            auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY")),
        )
    return _client


def close():
    global _client
    if _client is not None:
        _client.close()
        _client = None


def ingest_collection(name: str, docs: list[dict],
                      extra_props: list[str] | None = None) -> None:
    """(Re)create `name` and ingest docs with their OpenAI vectors.

    docs: list of {id, text, <extra props...>}. extra_props are stored as TEXT.
    """
    client = get_client()
    if client.collections.exists(name):
        client.collections.delete(name)
    props = [
        Property(name="doc_id", data_type=DataType.TEXT),
        Property(name="text", data_type=DataType.TEXT),
    ]
    for p in (extra_props or []):
        props.append(Property(name=p, data_type=DataType.TEXT))
    client.collections.create(name, properties=props)

    coll = client.collections.get(name)
    vectors = get_embeddings([d["text"] for d in docs])
    for d, v in zip(docs, vectors):
        properties = {"doc_id": d["id"], "text": d["text"]}
        for p in (extra_props or []):
            properties[p] = d.get(p, "")
        coll.data.insert(properties=properties, vector=v)
    time.sleep(2.0)  # let the HNSW index settle before querying


def vector_search(name: str, query_vector: list[float], k: int = 3,
                  extra_props: list[str] | None = None) -> list[dict]:
    """Nearest-neighbor search; returns ranked hits with similarity score."""
    coll = get_client().collections.get(name)
    resp = coll.query.near_vector(
        near_vector=query_vector, limit=k,
        return_metadata=MetadataQuery(distance=True),
    )
    hits = []
    for o in resp.objects:
        h = {
            "doc_id": o.properties.get("doc_id"),
            "text": o.properties.get("text"),
            "score": round(1 - (o.metadata.distance or 0), 4),
        }
        for p in (extra_props or []):
            h[p] = o.properties.get(p)
        hits.append(h)
    return hits


def rank_of(hits: list[dict], target_id: str) -> int:
    for i, h in enumerate(hits, 1):
        if h["doc_id"] == target_id:
            return i
    return 999
