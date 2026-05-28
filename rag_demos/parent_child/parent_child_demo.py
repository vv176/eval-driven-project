"""
Teaching demo — Parent-Child (small-to-big) retrieval.

Parent-child indexing buys TWO different things, and a student should see BOTH.
They fail for different reasons, so we show them as two scenarios:

  SCENARIO A — "Why thin chunks instead of one big chunk?"  (RETRIEVAL precision)
    A document-level embedding is the AVERAGE of everything in the document. When
    the answer is a small detail buried in a long, multi-topic doc, that doc's
    whole-chunk embedding is diluted and a short, wholly-on-topic distractor that
    does NOT contain the answer out-ranks it. Thin child chunks give the exact
    passage a focused embedding, so it ranks #1.
      naive big-chunk : index whole documents -> retrieves the WRONG doc -> fails
      parent-child    : index children -> right passage #1 -> expand to parent -> ok

  SCENARIO B — "Why return the PARENT instead of just the matched child?" (CONTEXT)
    Retrieval is fine here — the right child ranks #1 — but that child is a
    FRAGMENT containing a pronoun ("these limits") whose antecedent lives in a
    SIBLING child. Sending only the matched child cannot answer; following the
    parent_id pointer to the parent supplies the sibling and resolves it.
      child-only   : send only the matched child -> dangling reference -> fails
      parent-child : send the parent (all siblings) -> resolved -> ok

Run (from the eval-driven-project root):
    python -m rag_demos.parent_child.parent_child_demo
    python rag_demos/parent_child/parent_child_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from openai import OpenAI

from rag_demos.common import ingest_collection, vector_search, get_embedding, close

client = OpenAI()
MODEL = "gpt-4o"

# ── Scenario A corpus: the answer is a buried detail in a LONG document ──────
PARENTS_A = {
    "solo_plan": {
        "title": "ACME Solo (individual paid) Plan — Handbook",
        "children": [
            "Solo is our individual paid plan, designed for one person who has "
            "outgrown the free tier and wants more room and integrations.",
            "Onboarding: a guided setup wizard creates your first workspace and "
            "can import files from common cloud drives in a few clicks.",
            "Collaboration: Solo lets you share read-only links with people "
            "outside your account, with optional link expiry.",
            "Integrations: connect your calendar, your email, and up to two "
            "third-party apps of your choice from the marketplace.",
            "Mobile: the Solo plan includes the full mobile app with offline "
            "editing that syncs when you reconnect.",
            "Billing: Solo can be paid monthly or yearly; paying yearly saves "
            "roughly seventeen percent over the monthly rate.",
            "Data retention: when a Solo individual account is closed, its data "
            "is kept for 90 days and is then permanently deleted from our systems.",
            "Support: Solo includes community-forum support plus a weekly "
            "office-hours call hosted by the product team.",
        ],
    },
    "retention_overview": {
        "title": "Data Retention Overview",
        "children": [
            "ACME's data retention principles are designed to balance user "
            "privacy with legitimate operational needs.",
            "Retention windows differ by subscription tier and by the user's "
            "region, where local regulations may apply.",
            "You can review the exact retention window that applies to your own "
            "workspace in the dashboard under Privacy settings.",
        ],
    },
    "team_plan": {
        "title": "ACME Team Plan — Handbook",
        "children": [
            "Team is our plan for small groups who collaborate daily and need "
            "shared workspaces and admin controls.",
            "Onboarding: an admin invites members in bulk and assigns them to "
            "shared workspaces during setup.",
            "Permissions: Team adds role-based access control and audit logs for "
            "every shared workspace.",
            "Integrations: Team connects to single sign-on and to an unlimited "
            "number of marketplace apps.",
            "Mobile: the Team plan includes the mobile app with shared offline "
            "folders for the whole group.",
            "Billing: Team is billed per seat, monthly or yearly, and seats can "
            "be added or removed at any time.",
            "Data retention: when a Team account is closed, its data is kept for "
            "180 days and is then permanently deleted.",
            "Support: Team includes priority email support with a four-hour "
            "first-response target during business hours.",
        ],
    },
}
QUESTION_A = (
    "How long is a closed account's data kept before it is permanently "
    "deleted on the paid individual plan?"
)
MARKER_A = "90 day"

# ── Scenario B corpus: the matched child is a FRAGMENT with a dangling pronoun ──
# c0 holds the base value (100 GB). c1 is what matches a "Black Friday" query, but
# it says "these limits are doubled" — "these limits" is meaningless without c0.
PARENTS_B = {
    "pro_plan": {
        "title": "ACME Pro Plan — Limits & Promotions",
        "children": [
            "The Pro plan includes 100 GB of cloud storage and 10 team seats.",
            "During the annual Black Friday sale, these limits are doubled for "
            "the first year of any new subscription.",
            "The Pro plan also bundles priority email support and the full "
            "mobile app with offline mode.",
        ],
    },
    "free_plan": {
        "title": "ACME Free Plan — Limits",
        "children": [
            "The Free plan includes 2 GB of storage and a single seat, for "
            "evaluation only.",
            "Free plan accounts are limited to three active projects at a time.",
        ],
    },
}
QUESTION_B = "During the Black Friday sale, do the Pro plan's limits change, and if so to what values?"
MARKER_B = "200"


# ── Generic helpers over a parents dict ─────────────────────────────────────
def build_children(parents: dict) -> list[dict]:
    items = []
    for parent_id, p in parents.items():
        for i, text in enumerate(p["children"]):
            items.append({"id": f"{parent_id}#c{i}", "parent_id": parent_id, "text": text})
    return items


def build_documents(parents: dict) -> list[dict]:
    docs = []
    for parent_id, p in parents.items():
        docs.append({"id": parent_id, "text": p["title"] + ". " + " ".join(p["children"])})
    return docs


def parent_text(parents: dict, parent_id: str) -> str:
    p = parents[parent_id]
    return f"{p['title']}\n" + "\n".join(f"- {c}" for c in p["children"])


def ask_llm(question: str, context: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        messages=[
            {"role": "system", "content": (
                "Answer the user's question using ONLY the provided context. If "
                "the context does not let you state a specific number, say the "
                "number is not stated in the context. One sentence."
            )},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── Scenario A: precision (big chunk vs parent-child) ───────────────────────
def scenario_a():
    print("\n" + "#" * 74)
    print("# SCENARIO A — Why thin chunks, not one big chunk? (RETRIEVAL precision)")
    print("#" * 74)
    print(f"Question: {QUESTION_A!r}   (answer should mention '{MARKER_A}s')\n")
    qvec = get_embedding(QUESTION_A)

    ingest_collection("PC_A_Big", build_documents(PARENTS_A))
    big = vector_search("PC_A_Big", qvec, k=3)
    print("  NAIVE big-chunk retrieval (whole documents):")
    for i, h in enumerate(big, 1):
        print(f"    {i}. {h['doc_id']:20s} score={h['score']:.4f}")
    a_naive = ask_llm(QUESTION_A, big[0]["text"])
    print(f"    -> top doc '{big[0]['doc_id']}' fed to LLM")
    print(f"    NAIVE answer: {a_naive}")

    ingest_collection("PC_A_Small", build_children(PARENTS_A), extra_props=["parent_id"])
    child = vector_search("PC_A_Small", qvec, k=3, extra_props=["parent_id"])
    print("\n  PARENT-CHILD small-chunk retrieval (children):")
    for i, h in enumerate(child, 1):
        print(f"    {i}. {h['doc_id']:16s} score={h['score']:.4f}  | {h['text'][:55]}…")
    top = child[0]
    a_pc = ask_llm(QUESTION_A, parent_text(PARENTS_A, top["parent_id"]))
    print(f"    -> top child '{top['doc_id']}' -> follow parent_id "
          f"'{top['parent_id']}' -> feed PARENT")
    print(f"    PARENT-CHILD answer: {a_pc}")

    print(f"\n  Verdict A:  naive big-chunk got '{MARKER_A}s'? "
          f"{MARKER_A in a_naive.lower()}   |   parent-child? {MARKER_A in a_pc.lower()}")
    return (MARKER_A not in a_naive.lower()) and (MARKER_A in a_pc.lower())


# ── Scenario B: context (child-only vs parent-child) ────────────────────────
def scenario_b():
    print("\n" + "#" * 74)
    print("# SCENARIO B — Why the PARENT, not just the matched child? (CONTEXT)")
    print("#" * 74)
    print(f"Question: {QUESTION_B!r}   (answer should mention '{MARKER_B}')\n")
    qvec = get_embedding(QUESTION_B)

    ingest_collection("PC_B_Small", build_children(PARENTS_B), extra_props=["parent_id"])
    child = vector_search("PC_B_Small", qvec, k=3, extra_props=["parent_id"])
    print("  Child retrieval (same for both strategies below):")
    for i, h in enumerate(child, 1):
        print(f"    {i}. {h['doc_id']:16s} score={h['score']:.4f}  | {h['text'][:60]}…")
    top = child[0]
    print(f"\n  Matched child: {top['doc_id']}")
    print(f"    text: \"{top['text']}\"")

    b_child = ask_llm(QUESTION_B, top["text"])
    print("\n  ── CHILD-ONLY (send only the matched fragment) ──")
    print(f"    answer: {b_child}")

    b_pc = ask_llm(QUESTION_B, parent_text(PARENTS_B, top["parent_id"]))
    print("\n  ── PARENT-CHILD (follow parent_id, send the whole parent) ──")
    print(f"    parent fed:\n      " + parent_text(PARENTS_B, top["parent_id"]).replace("\n", "\n      "))
    print(f"    answer: {b_pc}")

    print(f"\n  Verdict B:  child-only got '{MARKER_B}'? "
          f"{MARKER_B in b_child}   |   parent-child? {MARKER_B in b_pc}")
    return (MARKER_B not in b_child) and (MARKER_B in b_pc)


def main():
    a_ok = scenario_a()
    b_ok = scenario_b()
    print("\n" + "=" * 74)
    print("  SUMMARY")
    print(f"    A (precision) — big-chunk fails, parent-child works : {a_ok}")
    print(f"    B (context)   — child-only fails, parent-child works : {b_ok}")
    print("=" * 74)
    if a_ok and b_ok:
        print("\n  ✅ Parent-child wins on BOTH axes:")
        print("     • thin child chunks retrieve the exact passage (vs a diluted big chunk)")
        print("     • expanding to the parent resolves dangling references the child lacks")
    close()


if __name__ == "__main__":
    main()
