"""
Teaching demo — HyDE (Hypothetical Document Embeddings).

WHY HyDE: a knowledge base often stores ANSWERS (declarative solution
statements), but users type QUESTIONS. A question and its answer use different
words and live in different regions of embedding space, so embedding the raw
QUESTION and searching retrieves the wrong things ("question-answer asymmetry").

HyDE's trick: ask an LLM to write a *hypothetical answer* to the question first,
then embed THAT and search. A fake answer lives in the same neighborhood as the
real answers, so retrieval lands on the right document.

This demo contrasts:
  NAIVE : embed the question  -> search        (misses the target)
  HyDE  : LLM writes a hypothetical answer
          -> embed the answer -> search        (finds the target)

Run (from the eval-driven-project root):
    python -m rag_demos.hyde.hyde_demo
    python rag_demos/hyde/hyde_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from openai import OpenAI

from rag_demos.common import (
    ingest_collection, vector_search, get_embedding, rank_of, close,
)

client = OpenAI()
MODEL = "gpt-4o"
TOP_K = 3
COLLECTION = "HydeDemo"

# A user QUESTION in everyday language.
QUESTION = "Why do my downloads crawl every evening around 8pm but feel fast again in the morning?"
TARGET_ID = "ans_isp_oversubscription"

# The corpus is entirely ANSWERS. The TARGET explains the real cause using
# technical vocabulary that shares almost NO words with the question (no
# "download / evening / morning / slow / fast"). The distractors DO share the
# question's everyday words but are the wrong answer — so embedding the raw
# question lands on distractors and misses the target. Only a hypothetical
# ANSWER (which describes the congestion mechanism) embeds near the target.
CORPUS = [
    {
        "id": "ans_isp_oversubscription",  # TARGET
        "text": (
            "Shared coaxial internet segments become oversubscribed during "
            "neighborhood peak hours: when many households pull traffic at once, "
            "your line contends for the same upstream capacity and effective "
            "throughput drops until demand subsides. A node split or a fiber "
            "upgrade from the provider relieves the peak-hour contention."
        ),
    },
    {
        "id": "ans_download_manager",
        "text": (
            "To speed up large downloads, pause other active downloads and use a "
            "download manager that splits each file into parallel segments."
        ),
    },
    {
        "id": "ans_morning_backups",
        "text": (
            "Scheduled backups often run in the morning and can briefly slow your "
            "connection early in the day. Reschedule them to overnight to keep "
            "mornings fast."
        ),
    },
    {
        "id": "ans_evening_updates",
        "text": (
            "Many apps auto-download their updates in the evening, which competes "
            "for bandwidth. Disable automatic evening updates to keep downloads "
            "responsive after work."
        ),
    },
    {
        "id": "ans_speedtest_router",
        "text": (
            "If downloads feel slow, run a speed test and restart the router. A "
            "stale session can throttle throughput until the device is rebooted."
        ),
    },
    {
        "id": "ans_dns_slow",
        "text": (
            "Pages that load slowly in the morning are sometimes caused by a slow "
            "DNS resolver. Switching DNS providers can make browsing feel faster."
        ),
    },
    {
        "id": "ans_wifi_distance",
        "text": (
            "Downloads are slower far from the router because the Wi-Fi signal "
            "weakens with distance. Move closer or use a wired link for full speed."
        ),
    },
    {
        "id": "ans_vpn_overhead",
        "text": (
            "A VPN can reduce download speed because of encryption overhead. "
            "Disconnect the VPN for large transfers to restore full speed."
        ),
    },
]


def generate_hypothetical_answer(question: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": (
                "You are a senior network/infrastructure engineer. In 2-3 "
                "sentences, explain the most likely ROOT CAUSE of the user's "
                "issue at the INFRASTRUCTURE level (ISP, network, hardware) using "
                "precise technical terminology for the mechanism. Describe the "
                "CAUSE, not user-side tips or step-by-step fixes. State it as "
                "fact — no hedging, no questions, no 'it depends'."
            )},
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content.strip()


def _show(title: str, hits, n=TOP_K):
    print(f"\n  {title}")
    for i, h in enumerate(hits, 1):
        mark = "  <-- TARGET" if h["doc_id"] == TARGET_ID else ""
        flag = "✓" if i <= n else " "
        print(f"    [{flag}] {i}. {h['doc_id']:22s} {h['score']:.4f}{mark}")


def main():
    print(f"Question: {QUESTION!r}")
    print(f"Target answer: {TARGET_ID!r}   top-K = {TOP_K}")

    # Ingest the answer corpus into Weaviate (vectors = OpenAI embeddings).
    ingest_collection(COLLECTION, [dict(d) for d in CORPUS])
    full_k = len(CORPUS)

    # NAIVE: search Weaviate with the embedded raw QUESTION.
    naive = vector_search(COLLECTION, get_embedding(QUESTION), k=full_k)
    _show("NAIVE — embed the QUESTION, then search", naive)
    naive_rank = rank_of(naive, TARGET_ID)

    # HyDE: generate a hypothetical answer, search Weaviate with ITS embedding.
    hypo = generate_hypothetical_answer(QUESTION)
    print(f"\n  Hypothetical answer (LLM):\n    \"{hypo}\"")
    hyde = vector_search(COLLECTION, get_embedding(hypo), k=full_k)
    _show("HyDE — embed the HYPOTHETICAL ANSWER, then search", hyde)
    hyde_rank = rank_of(hyde, TARGET_ID)

    print("\n" + "=" * 64)
    print(f"  TARGET RANK — naive: {naive_rank}   |   HyDE: {hyde_rank}")
    print("=" * 64)
    if naive_rank > TOP_K and hyde_rank <= TOP_K:
        print("\n  ✅ WOW: the raw question MISSES the answer; HyDE RETRIEVES it.")
    else:
        print("\n  (effect: naive should miss top-K, HyDE should hit it)")
    close()


if __name__ == "__main__":
    main()
