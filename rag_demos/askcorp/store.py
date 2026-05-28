"""
AskCorp store — 4 Weaviate collections (one per knowledge base), with
bring-your-own-vector ingest and a per-strategy search (bm25 / vector / hybrid).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import MetadataQuery, HybridFusion

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from rag.embedder import get_embedding, get_embeddings
from rag_demos.askcorp.corpus import CORPUS, INDEXES, collection_name

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


def ingest_all(reset: bool = True) -> None:
    client = get_client()
    for index_key, docs in CORPUS.items():
        name = collection_name(index_key)
        if reset and client.collections.exists(name):
            client.collections.delete(name)
        if not client.collections.exists(name):
            client.collections.create(
                name,
                properties=[
                    Property(name="doc_id", data_type=DataType.TEXT),
                    Property(name="text", data_type=DataType.TEXT),
                ],
            )
        coll = client.collections.get(name)
        vectors = get_embeddings([d["text"] for d in docs])
        for d, v in zip(docs, vectors):
            coll.data.insert(
                properties={"doc_id": d["id"], "text": d["text"]}, vector=v
            )
        print(f"  ingested {len(docs):2d} docs -> {name}")
    time.sleep(2.0)  # let HNSW indexes settle


def search(index_key: str, query: str, strategy: str = "hybrid",
           k: int = 3, alpha: float = 0.5) -> list[dict]:
    """Search one collection with the chosen strategy. Returns compact hits."""
    if index_key not in INDEXES:
        return [{"error": f"unknown index '{index_key}'",
                 "valid_indexes": list(INDEXES.keys())}]
    coll = get_client().collections.get(collection_name(index_key))
    qvec = None
    if strategy in ("vector", "hybrid"):
        qvec = get_embedding(query)

    if strategy == "bm25":
        resp = coll.query.bm25(
            query=query, limit=k, return_metadata=MetadataQuery(score=True)
        )
        score_of = lambda o: o.metadata.score or 0.0
    elif strategy == "vector":
        resp = coll.query.near_vector(
            near_vector=qvec, limit=k, return_metadata=MetadataQuery(distance=True)
        )
        score_of = lambda o: round(1 - (o.metadata.distance or 0), 4)
    elif strategy == "hybrid":
        resp = coll.query.hybrid(
            query=query, vector=qvec, alpha=alpha, limit=k,
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=MetadataQuery(score=True),
        )
        score_of = lambda o: round(o.metadata.score or 0.0, 4)
    else:
        return [{"error": f"unknown strategy '{strategy}'",
                 "valid_strategies": ["bm25", "vector", "hybrid"]}]

    hits = []
    for o in resp.objects:
        text = o.properties.get("text", "")
        hits.append({
            "index": index_key,
            "doc_id": o.properties.get("doc_id"),
            "score": score_of(o),
            "snippet": text[:240] + ("…" if len(text) > 240 else ""),
        })
    return hits
