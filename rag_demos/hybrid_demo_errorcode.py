"""
Teaching demo #1b — Hybrid search with an OBVIOUS relevant document.

Same lesson as hybrid_demo.py (hybrid beats vector-only and BM25-only), but the
correct document is human-obvious: the query contains a gibberish error code
(XQJ7741) and ONLY the target document contains that same code. Any student can
glance at the query + docs and say "doc 1 is the answer."

The wow is that neither pure method puts it in top-K anyway:
  - PURE VECTOR : the error code is gibberish, so embeddings can't 'see' it;
    on-topic paraphrases of the symptom out-rank the target.
  - PURE BM25   : the target's only keyword match is the code; several
    off-topic docs each match MORE common query words, so their summed BM25
    out-votes the single code match.
  - HYBRID      : the target is the only doc that is BOTH code-matching (BM25)
    AND on-topic (vector), so relative-score fusion lifts it into top-K.

Run (from the eval-driven-project root):
    python -m rag_demos.hybrid_demo_errorcode
    python rag_demos/hybrid_demo_errorcode.py   # also works (self-bootstrapping)
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

COLLECTION = "HybridDemoCode"
TOP_K = 3

# Query carries a gibberish error code AND a natural-language symptom.
QUERY = "my smart TV keeps buffering video and shows error code XQJ7741 every few minutes"
TARGET_ID = "fix_xqj7741"

CORPUS = [
    # ---- TARGET: obvious to a human — the ONLY doc that explains AND fixes
    # XQJ7741 in the smart-TV streaming context. On-topic (shares "buffering")
    # + has the code. Balanced on both axes. ----
    {
        "id": "fix_xqj7741",
        "text": (
            "On the streaming app, XQJ7741 means the secure clock drifted from "
            "the license server, so the picture keeps buffering and stalling "
            "mid-stream. Re-pair the device in Settings then Account to clear "
            "XQJ7741 and stop the buffering."
        ),
    },
    # ---- LEXICAL specialists: off-topic devices that share the query's
    # GENERIC process words ("shows ... error ... code ... every few minutes ...
    # keeps") but NOT the code and NOT the topic. Many generic matches ->
    # high BM25; wrong domain -> low-ish vector. ----
    {
        "id": "lex_car",
        "text": (
            "My car dashboard shows an error code every few minutes while "
            "driving. The dashboard error keeps flashing, and it shows again "
            "every few minutes on the console."
        ),
    },
    {
        "id": "lex_fitness",
        "text": (
            "My fitness watch shows an error code every few minutes during a "
            "run. The watch error keeps appearing, and an error shows every few "
            "minutes on the band."
        ),
    },
    {
        "id": "lex_thermostat",
        "text": (
            "The thermostat shows an error code every few minutes. This error "
            "keeps showing, and an error code shows every few minutes on the "
            "heating panel."
        ),
    },
    {
        "id": "lex_printer",
        "text": (
            "The office printer shows an error code every few minutes. The "
            "printer error keeps showing, and an error code shows every few "
            "minutes on the display."
        ),
    },
    # ---- SEMANTIC specialists: on-topic smart-TV buffering paraphrases, WRONG
    # fix, NO code. Share the topic words (smart TV buffering video) -> high
    # vector, modest BM25. ----
    {
        "id": "sem_cache",
        "text": (
            "When your smart TV keeps buffering video, clearing the app cache "
            "often frees the decoder and smooths video playback."
        ),
    },
    {
        "id": "sem_update",
        "text": (
            "Smart TV video buffering usually clears after a video app update; "
            "install the latest version so video stops buffering."
        ),
    },
    {
        "id": "sem_router",
        "text": (
            "If your smart TV keeps buffering video, a congested router is a "
            "common cause; reboot the router so video stops buffering."
        ),
    },
]


def _client():
    return weaviate.connect_to_weaviate_cloud(
        cluster_url=os.getenv("WEAVIATE_URL"),
        auth_credentials=Auth.api_key(os.getenv("WEAVIATE_API_KEY")),
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
    time.sleep(2.0)  # let the HNSW vector index settle


def _rank_of(results: list[str], target: str) -> int:
    for i, doc_id in enumerate(results, 1):
        if doc_id == target:
            return i
    return 999


def _run_mode(coll, mode: str, qvec, n: int):
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
        marker = "  <-- TARGET (has code XQJ7741)" if doc_id == TARGET_ID else ""
        intop = "✓" if i <= TOP_K else " "
        print(f"    [{intop}] {i:2d}. {doc_id:16s} score={score:.4f}{marker}")


def main():
    print(f"Query: {QUERY!r}")
    print(f"Target doc: {TARGET_ID!r}  (the only doc containing the code)   top-K = {TOP_K}")

    client = _client()
    try:
        _reset_and_ingest(client)
        coll = client.collections.get(COLLECTION)
        qvec = get_embedding(QUERY)
        n = len(CORPUS)

        v = _run_mode(coll, "vector", qvec, n)
        b = _run_mode(coll, "bm25", qvec, n)
        h = _run_mode(coll, "hybrid", qvec, n)

        _print_mode("PURE VECTOR (semantic only — blind to the code)", v)
        _print_mode("PURE BM25 (keyword only — out-voted by off-topic docs)", b)
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
            print("\n  ✅ WOW: the obviously-relevant doc (it literally has the code) is")
            print("     MISSED by both pure methods but RECOVERED by hybrid.")
        else:
            print("\n  ❌ Effect not achieved yet. Need: vector>K AND bm25>K AND hybrid<=K.")
        return 0 if wow else 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
