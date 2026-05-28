"""
Teaching demo #1 — Why hybrid (vector + BM25) beats either alone.

The corpus is engineered so that for one query:
  - PURE VECTOR  misses the correct doc from top-K (semantic-specialist
    distractors paraphrase the symptom and crowd it out)
  - PURE BM25    misses the correct doc from top-K (lexical-specialist
    distractors stuff the query keywords and crowd it out)
  - HYBRID       surfaces the correct doc in top-K (it is the only doc that
    scores well on BOTH axes, so relative-score fusion lifts it)

Run (from the eval-driven-project root):
    python -m rag_demos.hybrid_demo
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable so `from rag.embedder import ...` works
# whether this file is run as a module (python -m rag_demos.hybrid_demo) OR
# directly (python rag_demos/hybrid_demo.py from an IDE run button).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Property, DataType
from weaviate.classes.query import MetadataQuery, HybridFusion
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from rag.embedder import get_embedding, get_embeddings

COLLECTION = "HybridDemo"
TOP_K = 3

# The user's query: a fine internet, yet video buffers. The *correct* fix is
# the hardware-acceleration one.
QUERY = "video keeps buffering even though my internet speed test comes back fine"
TARGET_ID = "fix_hwaccel"

# ── Corpus ────────────────────────────────────────────────────────────
# target  : balanced — shares a few query keywords AND is the real answer
# lex_*   : keyword-stuffed (video/buffering/internet/speed test/fine), wrong topic
# sem_*   : paraphrased symptom (synonyms, low keyword overlap), wrong fix
CORPUS = [
    # ---- TARGET ----
    # Shares the high-IDF symptom word "buffering" with the query, but almost
    # none of the common query terms (video/internet/fine/speed test). It is
    # the only doc that is BOTH the correct fix AND keyword-linked to the
    # query's key symptom — so neither pure axis ranks it first, but fusion does.
    {
        "id": "fix_hwaccel",
        "text": (
            "Persistent buffering, even when everything else looks healthy, is "
            "almost always hardware acceleration fighting your graphics driver. "
            "Switch off hardware decoding in the player settings to resolve it."
        ),
    },
    # ---- LEXICAL specialists (win BM25, semantically OFF-TOPIC) ----
    # Each hammers ONE query word in a totally different domain (athletics,
    # dining, banking, music). High keyword match, but the embedding is dragged
    # far away from "video buffering troubleshooting".
    {
        "id": "lex_sprint",
        "text": (
            "Speed test at the track today: my sprint speed test felt fine, the "
            "second speed test was fine too, and the coach said my speed test "
            "splits looked fine across every speed test."
        ),
    },
    {
        "id": "lex_dining",
        "text": (
            "Such a fine restaurant — fine dining, fine wine, fine service. The "
            "fine print on the tasting menu was fine, the bill was fine, and "
            "honestly everything about the evening was just fine."
        ),
    },
    {
        "id": "lex_bank",
        "text": (
            "Internet banking note: my internet portal internet session on the "
            "internet bank internet site used internet cookies, and the "
            "internet statement loaded over internet just fine."
        ),
    },
    {
        "id": "lex_audio",
        "text": (
            "In the audio workstation, raise the buffering size: a larger "
            "buffering window cuts dropouts. Set buffering to 2048 samples, "
            "test the buffering, and the buffering latency finally settles."
        ),
    },
    # ---- SEMANTIC specialists (win vector, wrong fix) ----
    # Share only the common word "video" + a strong paraphrase of the symptom.
    # NO "buffering", NO "keeps", no rare token → near-zero BM25, high vector.
    {
        "id": "sem_update",
        "text": (
            "A video that stutters on a fast connection is usually an outdated "
            "app; update to the newest version to smooth out playback."
        ),
    },
    {
        "id": "sem_cache",
        "text": (
            "When a video freezes despite plenty of bandwidth, clearing the "
            "local cache frees the decoder and restores smooth playback."
        ),
    },
    {
        "id": "sem_extension",
        "text": (
            "A video that pauses on a reliable network is often a browser "
            "add-on intercepting the stream; disable add-ons to fix it."
        ),
    },
    {
        "id": "sem_dns",
        "text": (
            "A video that stalls while the network looks healthy can come from "
            "a slow DNS resolver; switch DNS providers to steady it."
        ),
    },
]


def _client():
    url = os.getenv("WEAVIATE_URL")
    key = os.getenv("WEAVIATE_API_KEY")
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=url, auth_credentials=Auth.api_key(key)
    )


def _reset_and_ingest(client) -> None:
    if client.collections.exists(COLLECTION):
        client.collections.delete(COLLECTION)
    client.collections.create(
        COLLECTION,
        properties=[
            Property(name="doc_id", data_type=DataType.TEXT),
            Property(name="text", data_type=DataType.TEXT),
        ],
    )
    coll = client.collections.get(COLLECTION)
    vectors = get_embeddings([d["text"] for d in CORPUS])
    for d, v in zip(CORPUS, vectors):
        coll.data.insert(properties={"doc_id": d["id"], "text": d["text"]}, vector=v)
    # Let the HNSW vector index settle before querying (otherwise the first
    # near_vector call can return empty while BM25/hybrid already work).
    import time
    time.sleep(2.0)


def _rank_of(results: list[str], target: str) -> int:
    """1-based rank of target in results, or 999 if absent."""
    for i, doc_id in enumerate(results, 1):
        if doc_id == target:
            return i
    return 999


def _run_mode(coll, mode: str, qvec, n: int):
    """Return list of (doc_id, score) for the full corpus, ranked by `mode`."""
    if mode == "vector":
        resp = coll.query.near_vector(
            near_vector=qvec, limit=n, return_metadata=MetadataQuery(distance=True)
        )
        return [(o.properties["doc_id"], 1 - (o.metadata.distance or 0)) for o in resp.objects]
    if mode == "bm25":
        resp = coll.query.bm25(
            query=QUERY, limit=n, return_metadata=MetadataQuery(score=True)
        )
        return [(o.properties["doc_id"], o.metadata.score or 0.0) for o in resp.objects]
    if mode == "hybrid":
        resp = coll.query.hybrid(
            query=QUERY, vector=qvec, alpha=0.5, limit=n,
            fusion_type=HybridFusion.RELATIVE_SCORE,
            return_metadata=MetadataQuery(score=True),
        )
        return [(o.properties["doc_id"], o.metadata.score or 0.0) for o in resp.objects]
    raise ValueError(mode)


def _print_mode(name: str, ranked: list[tuple[str, float]]):
    print(f"\n  {name}")
    for i, (doc_id, score) in enumerate(ranked, 1):
        marker = "  <-- TARGET" if doc_id == TARGET_ID else ""
        intop = "✓" if i <= TOP_K else " "
        print(f"    [{intop}] {i:2d}. {doc_id:16s} score={score:.4f}{marker}")


def main():
    print(f"Query: {QUERY!r}")
    print(f"Target doc: {TARGET_ID!r}   top-K = {TOP_K}")

    client = _client()
    try:
        _reset_and_ingest(client)
        coll = client.collections.get(COLLECTION)
        qvec = get_embedding(QUERY)
        n = len(CORPUS)

        v = _run_mode(coll, "vector", qvec, n)
        b = _run_mode(coll, "bm25", qvec, n)
        h = _run_mode(coll, "hybrid", qvec, n)

        _print_mode("PURE VECTOR (semantic only)", v)
        _print_mode("PURE BM25 (keyword only)", b)
        _print_mode("HYBRID (alpha=0.5, relative-score fusion)", h)

        rv = _rank_of([d for d, _ in v], TARGET_ID)
        rb = _rank_of([d for d, _ in b], TARGET_ID)
        rh = _rank_of([d for d, _ in h], TARGET_ID)

        print("\n" + "=" * 60)
        print("  TARGET RANK BY MODE")
        print(f"    pure vector : {rv}   {'(in top-K)' if rv <= TOP_K else '(MISSED top-K)'}")
        print(f"    pure bm25   : {rb}   {'(in top-K)' if rb <= TOP_K else '(MISSED top-K)'}")
        print(f"    hybrid      : {rh}   {'(in top-K)' if rh <= TOP_K else '(MISSED top-K)'}")
        print("=" * 60)

        wow = rv > TOP_K and rb > TOP_K and rh <= TOP_K
        if wow:
            print("\n  ✅ WOW: target is MISSED by both pure methods but RECOVERED by hybrid.")
        else:
            print("\n  ❌ Effect not achieved yet. Need: vector>K AND bm25>K AND hybrid<=K.")
        return 0 if wow else 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
