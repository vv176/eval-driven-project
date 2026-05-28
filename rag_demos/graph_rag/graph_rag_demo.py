"""
Teaching demo — Graph RAG (knowledge-graph traversal).

WHY: some questions require CONNECTING facts across many documents — a
multi-hop or transitive query. Plain vector RAG retrieves the top-k most
similar documents and lets the LLM answer from them, but if the answer depends
on relationships spread across MORE documents than fit in top-k (or that no
single document states), vector RAG returns an INCOMPLETE answer.

A KNOWLEDGE GRAPH stores facts as nodes (entities) and edges (relationships).
Instead of similarity search, you TRAVERSE the graph to compute the answer
exactly — e.g. the full transitive set of services impacted by an outage.

This demo contrasts, for "what is impacted if auth-service goes down?":
  VECTOR RAG : embed the question, retrieve top-k "X depends on Y" facts, let
               the LLM list what it sees      -> misses the INDIRECT impact
  GRAPH RAG  : traverse the dependency graph (all transitive dependents)
               -> the COMPLETE blast radius

Library: networkx (a standard, well-known graph library).

Run (from the eval-driven-project root):
    python -m rag_demos.graph_rag.graph_rag_demo
    python rag_demos/graph_rag/graph_rag_demo.py
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
VECTOR_K = 5  # plain RAG retrieves this many fact-docs
COLLECTION = "GraphRagDemo"

# A "X depends on Y" edge means: if Y is down, X is impacted.
# The knowledge graph is just these edges as (child, parent) pairs.
DEPENDENCIES = [
    ("web-frontend", "api-gateway"),
    ("mobile-app", "api-gateway"),
    ("api-gateway", "auth-service"),
    ("api-gateway", "catalog-service"),
    ("payments-service", "auth-service"),
    ("payments-service", "ledger-service"),
    ("checkout-service", "payments-service"),
    ("order-service", "payments-service"),
    ("order-service", "inventory-service"),
    ("analytics-service", "order-service"),
    ("notification-service", "auth-service"),
    ("catalog-service", "search-service"),
]

OUTAGE = "auth-service"
QUESTION = (
    "If the auth-service has an outage, which services are impacted, "
    "directly or indirectly?"
)


# ── Knowledge graph (networkx) ───────────────────────────────────────────
def build_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    for child, parent in DEPENDENCIES:
        g.add_edge(child, parent, label="depends_on")
    return g


def graph_rag_answer(g: nx.DiGraph, outage: str) -> list[str]:
    """Everything that transitively DEPENDS ON `outage` is impacted.
    With edges child->parent (depends_on), that is the set of ancestors."""
    return sorted(nx.ancestors(g, outage))


# ── Plain vector RAG over the edge facts ─────────────────────────────────
def edge_docs() -> list[dict]:
    return [
        {"id": f"{c}->{p}", "text": f"The {c} depends on the {p}."}
        for c, p in DEPENDENCIES
    ]


def vector_rag_answer(question: str) -> tuple[list[str], list[str]]:
    ingest_collection(COLLECTION, edge_docs())
    hits = vector_search(COLLECTION, get_embedding(question), k=VECTOR_K)
    retrieved = [h["text"] for h in hits]
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[
            {"role": "system", "content": (
                "You answer ONLY from the provided dependency facts. List the "
                "services that would be impacted if auth-service is down, based "
                "strictly on the facts given. Return a comma-separated list of "
                "service names only."
            )},
            {"role": "user", "content": "Facts:\n- " + "\n- ".join(retrieved)
                                        + f"\n\nQuestion: {question}"},
        ],
    )
    answer_text = resp.choices[0].message.content.strip()
    names = [s.strip(" .") for s in answer_text.replace("\n", ",").split(",") if s.strip(" .")]
    return retrieved, names


def main():
    print(f"Question: {QUESTION!r}\n")
    g = build_graph()
    print(f"  Knowledge graph: {g.number_of_nodes()} services, "
          f"{g.number_of_edges()} 'depends_on' edges.\n")

    # Plain vector RAG
    retrieved, vec_names = vector_rag_answer(QUESTION)
    print(f"  ── VECTOR RAG (top-{VECTOR_K} similar facts) ──")
    print("    retrieved facts:")
    for r in retrieved:
        print(f"      • {r}")
    print(f"    answer: {sorted(vec_names)}")

    # Graph RAG
    graph_impacted = graph_rag_answer(g, OUTAGE)
    print(f"\n  ── GRAPH RAG (traverse transitive dependents) ──")
    print(f"    answer: {graph_impacted}")

    # Compare
    missed = sorted(set(graph_impacted) - set(vec_names))
    print("\n" + "=" * 64)
    print(f"  Complete impact set (ground truth) : {len(graph_impacted)} services")
    print(f"  Vector RAG found                   : {len(set(vec_names) & set(graph_impacted))}")
    print(f"  Vector RAG MISSED (indirect)       : {missed}")
    print("=" * 64)
    if missed:
        print("\n  ✅ WOW: vector RAG, limited to top-k facts, misses the INDIRECT")
        print("     (multi-hop) impact. Graph traversal returns the full blast radius.")
    else:
        print("\n  (expected vector RAG to miss some indirect dependents)")
    close()


if __name__ == "__main__":
    main()
