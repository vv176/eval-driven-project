"""
AskCorp — agentic RAG demo runner.

Runs a curated set of questions, each chosen to elicit a different dynamic
behavior, and prints the LLM's live retrieval decisions plus a per-question
"behaviors observed" summary.

Run (from the eval-driven-project root):
    python -m rag_demos.askcorp.run                 # all demo questions
    python -m rag_demos.askcorp.run "your question" # ask one ad-hoc question
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rag_demos.askcorp.agent import answer_question
from rag_demos.askcorp.store import close

# Each question is picked to showcase a behavior (label is for the instructor).
DEMO_QUESTIONS = [
    ("Single-index routing (+ rewrite)",
     "How many casual leaves do I get in a year?"),
    ("Conditional rewrite — NONE (query already clean)",
     "earned leave carry-over limit"),
    ("Strategy = bm25 (exact code)",
     "What does policy HR-CL-12 cover?"),
    ("Strategy = hybrid (name + concept)",
     "Does the Business plan's SLA actually give customers money back when we have downtime?"),
    ("Fan-out across 2 indexes (+ multi-query)",
     "What's our refund policy, and how do I actually issue a refund in the admin panel?"),
    ("Multi-query variations, same index (+ rewrite)",
     "What perks and time-off can someone who just joined make use of right away?"),
    ("Adaptive-K re-query (+ rewrite)",
     "What did we decide about the team restructuring this quarter?"),
]


def _print_result(label: str, result: dict):
    print("\n" + "═" * 78)
    print(f"  Q [{label}]")
    print(f"  {result['user_query']}")
    print("═" * 78)
    # decisions were printed live by the agent (verbose); now the summary + answer
    b = result["behaviors"]
    print("\n  ── Behaviors observed ──")
    print(f"    searches run     : {b['num_searches']}")
    print(f"    indexes routed   : {b['indexes_routed']}  (fan-out: {b['fan_out']})")
    print(f"    query rewritten? : {b['any_rewrite']}")
    print(f"    multi-query?     : {b['multi_query']}  (same-index variations: {b['same_index_multi_query']})")
    print(f"    strategies used  : {b['strategies_used']}")
    print(f"    adaptive-K?      : {b['adaptive_k']}")
    print("\n  ── Answer ──")
    print(f"    {result['answer']}")
    print(f"    sources: {result['sources_used']}")


def main():
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(f"\nQuestion: {q}\n")
        res = answer_question(q, verbose=True)
        _print_result("ad-hoc", res)
        close()
        return

    for label, q in DEMO_QUESTIONS:
        print("\n" + "━" * 78)
        print(f"  [{label}]  {q}")
        print("━" * 78)
        res = answer_question(q, verbose=True)
        _print_result(label, res)

    close()


if __name__ == "__main__":
    main()
