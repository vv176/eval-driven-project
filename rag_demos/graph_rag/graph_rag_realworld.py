"""
Teaching demo — Graph RAG over REAL-WORLD prose documents (multi-hop reasoning).

Unlike the toy "X depends on Y" graph, here the knowledge graph is EXTRACTED from
natural-language documents by an LLM, then traversed to answer a question whose
answer is spread across several documents.

The question:  "Who is the CEO of the company that owns the mapping engine
                RideLink uses for navigation?"

The answer requires THREE hops, each fact in a DIFFERENT document:
    RideLink --uses--> GeoPilot (engine)        [doc: ridelink_product]
    GeoPilot --owned_by--> Atlas Mobility Group  [doc: geopilot_profile]
    Atlas Mobility Group --ceo--> Priya Nair     [doc: atlas_profile]

Why PLAIN RAG fails:
  - The answer doc (atlas_profile / "Priya Nair") shares NONE of the query's
    distinctive words (RideLink, mapping engine, navigation), so vector
    similarity never retrieves it.
  - Meanwhile a trap doc says RideLink's OWN ceo is Tom Beck — high similarity to
    "CEO ... RideLink" — so plain RAG tends to answer "Tom Beck" (wrong).

Why GRAPH RAG works:
  - Extract a knowledge graph (subject, relation, object) from ALL docs, then
    traverse the connected neighborhood of "RideLink" to gather the ownership
    chain — structure, not similarity — and answer "Priya Nair".

Run (from the eval-driven-project root):
    python -m rag_demos.graph_rag.graph_rag_realworld
    python rag_demos/graph_rag/graph_rag_realworld.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import networkx as nx
from openai import OpenAI

from rag_demos.common import ingest_collection, vector_search, get_embedding, close

client = OpenAI()
MODEL = "gpt-4o"
PLAIN_K = 4
COLLECTION = "GraphRagRealWorld"

QUESTION = "Who is the CEO of the company that owns the mapping engine RideLink uses for navigation?"
ANSWER_MARKER = "priya nair"
TRAP_MARKER = "tom beck"  # RideLink's own CEO — the wrong answer plain RAG tends to give

DOCS = [
    {  # hop 1: RideLink uses GeoPilot
        "id": "ridelink_product",
        "text": (
            "RideLink is a popular ride-hailing app operating in over 30 cities. "
            "Its turn-by-turn navigation is powered by the GeoPilot mapping "
            "engine, which RideLink licenses from a third party rather than "
            "building its own maps in-house."
        ),
    },
    {  # TRAP: RideLink's own CEO (NOT the answer)
        "id": "ridelink_leadership",
        "text": (
            "RideLink was founded in 2016 and is led by its chief executive "
            "officer, Tom Beck, who previously ran a same-day logistics startup."
        ),
    },
    {  # hop 2: GeoPilot owned by Atlas Mobility Group
        "id": "geopilot_profile",
        "text": (
            "GeoPilot builds high-precision routing and mapping engines used by "
            "several mobility apps. In 2023, GeoPilot was acquired by Atlas "
            "Mobility Group and now operates as a wholly owned subsidiary."
        ),
    },
    {  # hop 3 (ANSWER): Atlas Mobility Group's CEO is Priya Nair
        "id": "atlas_profile",
        "text": (
            "Atlas Mobility Group is a holding company with interests across "
            "transportation and logistics. Priya Nair has served as the chief "
            "executive of Atlas Mobility Group since 2024, having joined from "
            "the freight industry."
        ),
    },
    # ── distractors / graph richness ──
    {
        "id": "geopilot_tech",
        "text": (
            "The GeoPilot engine relies on a proprietary lane-level routing "
            "algorithm and real-time traffic fusion to compute fast routes."
        ),
    },
    {
        "id": "ridelink_funding",
        "text": (
            "RideLink raised a 200 million dollar Series C round led by "
            "Northwind Capital to expand into new regional markets."
        ),
    },
    {
        "id": "atlas_portfolio",
        "text": (
            "Beyond GeoPilot, Atlas Mobility Group also owns FleetCore, a "
            "fleet-management platform used by commercial delivery operators."
        ),
    },
    {
        "id": "mapwise_profile",
        "text": (
            "MapWise is a competing mapping-technology company. Its chief "
            "executive, Daniel Cho, has focused the firm on pedestrian routing."
        ),
    },
    {
        "id": "zipride_profile",
        "text": (
            "ZipRide, a direct competitor to RideLink, builds its own in-house "
            "maps and is led by chief executive Lena Frost."
        ),
    },
    {
        "id": "geopilot_customers",
        "text": (
            "Besides RideLink, the GeoPilot engine also powers navigation for "
            "several grocery-delivery applications across Europe."
        ),
    },
]


def ask(question: str, context: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[
            {"role": "system", "content": (
                "Answer the question using ONLY the provided context. Name the "
                "specific person if the context allows it; if the chain of facts "
                "needed is not fully present, say you cannot determine it. One "
                "sentence."
            )},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── PLAIN RAG ────────────────────────────────────────────────────────────
def plain_rag():
    ingest_collection(COLLECTION, DOCS)
    hits = vector_search(COLLECTION, get_embedding(QUESTION), k=PLAIN_K)
    print(f"  top-{PLAIN_K} retrieved docs (by vector similarity):")
    for i, h in enumerate(hits, 1):
        print(f"    {i}. {h['doc_id']:20s} score={h['score']:.4f}")
    has_answer_doc = any(h["doc_id"] == "atlas_profile" for h in hits)
    print(f"    (answer doc 'atlas_profile' retrieved? {has_answer_doc})")
    context = "\n\n".join(f"[{h['doc_id']}] {h['text']}" for h in hits)
    return ask(QUESTION, context)


# ── GRAPH RAG ────────────────────────────────────────────────────────────
def extract_kg(docs: list[dict]) -> list[tuple[str, str, str]]:
    """LLM extracts (subject | relation | object) triples from ALL docs at once
    (one call → consistent canonical entity names)."""
    joined = "\n\n".join(f"[{d['id']}] {d['text']}" for d in docs)
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[
            {"role": "system", "content": (
                "You build a knowledge graph from documents. Extract factual "
                "relationships as triples, one per line, formatted exactly as:\n"
                "subject | relation | object\n"
                "Use SHORT, CANONICAL entity names and reuse the exact same name "
                "for the same entity everywhere (e.g. always 'Atlas Mobility "
                "Group'). Prefer these relations when they fit: uses, owned_by, "
                "ceo, founded_by, competitor_of, customer_of, owns. Output only "
                "the triples, no commentary."
            )},
            {"role": "user", "content": joined},
        ],
    )
    triples = []
    for line in resp.choices[0].message.content.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3 and all(parts):
            triples.append((parts[0], parts[1], parts[2]))
    return triples


def build_graph(triples) -> nx.DiGraph:
    g = nx.DiGraph()
    for s, r, o in triples:
        g.add_edge(s, o, relation=r)
    return g


def graph_rag():
    triples = extract_kg(DOCS)
    print("  Knowledge graph extracted from the documents (triples):")
    for s, r, o in triples:
        print(f"    {s}  --{r}-->  {o}")
    g = build_graph(triples)

    # seed = entities named in the question
    seeds = [n for n in g.nodes if n.lower() in QUESTION.lower()]
    print(f"\n  seed entities found in the question: {seeds}")

    # gather the connected neighborhood (multi-hop), direction-agnostic.
    # The graph gives us CONNECTIVITY; the facts we hand the LLM come from the
    # ORIGINAL triples filtered to those nodes, so parallel relations between
    # the same pair (e.g. ceo AND founded_by) are not lost.
    sub_nodes: set[str] = set()
    for s in seeds:
        sub_nodes |= set(nx.ego_graph(g, s, radius=3, undirected=True).nodes)
    sub_triples = [
        (s, r, o) for (s, r, o) in triples if s in sub_nodes and o in sub_nodes
    ]
    print(f"\n  traversed sub-graph around the seed ({len(sub_triples)} facts):")
    for s, r, o in sub_triples:
        print(f"    {s}  --{r}-->  {o}")

    facts = "\n".join(f"- {s} {r} {o}" for s, r, o in sub_triples)
    return ask(QUESTION, f"Knowledge-graph facts:\n{facts}")


def main():
    print(f"Question: {QUESTION!r}")
    print(f"Correct answer: Priya Nair  |  trap (RideLink's own CEO): Tom Beck\n")

    print("#" * 74)
    print("# PLAIN RAG (top-k vector similarity → LLM)")
    print("#" * 74)
    plain_answer = plain_rag()
    print(f"\n  PLAIN RAG answer: {plain_answer}")

    print("\n" + "#" * 74)
    print("# GRAPH RAG (extract knowledge graph → traverse → LLM)")
    print("#" * 74)
    graph_answer = graph_rag()
    print(f"\n  GRAPH RAG answer: {graph_answer}")

    pa, ga = plain_answer.lower(), graph_answer.lower()
    print("\n" + "=" * 74)
    print(f"  PLAIN RAG got 'Priya Nair'?  {ANSWER_MARKER in pa}"
          f"   (fell for trap 'Tom Beck'? {TRAP_MARKER in pa})")
    print(f"  GRAPH RAG got 'Priya Nair'?  {ANSWER_MARKER in ga}")
    print("=" * 74)
    if ANSWER_MARKER not in pa and ANSWER_MARKER in ga:
        print("\n  ✅ WOW: the answer lives in a doc that shares no words with the query,")
        print("     so vector RAG never retrieves it; the knowledge graph connects")
        print("     RideLink → GeoPilot → Atlas Mobility Group → Priya Nair by structure.")
    else:
        print("\n  (target: plain RAG misses Priya Nair, graph RAG gets it)")
    close()


if __name__ == "__main__":
    main()
