"""
AskCorp — agentic RAG orchestrator.

Every retrieval decision is made by the LLM and exposed as a tool call:
  - WHICH index(es) to search        (routing / fan-out)
  - WHETHER to rewrite the query     (conditional rewriting)
  - HOW MANY query variations        (multi-query)
  - WHICH strategy: bm25/vector/hybrid
  - HOW MANY results (k)             + re-query with a bigger k if results are weak

The loop returns a structured trace so a runner can show the dynamism.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from openai import OpenAI

from rag_demos.askcorp.corpus import INDEXES
from rag_demos.askcorp.store import search

client = OpenAI()
MODEL = "gpt-4o"
MAX_ITERS = 8

_index_block = "\n".join(f"  - {k}: {v}" for k, v in INDEXES.items())

SYSTEM_PROMPT = f"""You are AskCorp, an internal company assistant backed by FOUR separate
knowledge bases (indexes). You answer employee questions by RETRIEVING from the
right index(es) and then writing a grounded answer that cites the documents you used.

The four indexes and what each contains:
{_index_block}

You have one retrieval tool, `search_knowledge_base`. You decide, every time:

1. ROUTING — which index to search. Pick the index whose description matches the
   question. If a question spans more than one area (for example a customer-facing
   POLICY *and* the internal HOW-TO to carry it out), search MULTIPLE indexes.
   Search only the indexes you actually need — don't fan out for a narrow question.

2. STRATEGY — choose per search:
   - "bm25"   for exact identifiers: policy codes (e.g. HR-CL-12), error codes,
     product names, anything where the EXACT token must match.
   - "vector" for conceptual / paraphrased questions where wording will differ
     from the documents.
   - "hybrid" when the query MIXES an exact term (a plan name, product name, or
     partial identifier) with a conceptual question, OR whenever you are unsure —
     hybrid is the safe default that blends keyword and meaning.

3. REWRITING — if the user's wording is casual, vague, or unlikely to match the
   document vocabulary, REWRITE it into a precise query in `query_text`. BUT if
   the user's input is ALREADY a concise keyword query (a few words, no
   conversational filler like "how many" or "can I"), copy it into `query_text`
   VERBATIM — do not change a single word. Rewriting a query that is already
   clean only adds noise.

4. MULTI-QUERY — for a broad or multi-part question, issue SEVERAL focused query
   variations (multiple search calls), possibly against different indexes, to
   cover each part.

5. ADAPTIVE RE-QUERY — begin each line of inquiry with a SMALL k=3 to keep the
   answer focused (retrieving a huge k "just in case" is discouraged and wastes
   context). Then JUDGE whether those top results actually CONTAIN the answer.
   The top hits are often near-misses that merely MENTION the topic (a survey, a
   teaser, a seating change) but state no decision, number, or procedure. When
   that happens, DO NOT give up and DO NOT answer from a near-miss: re-query the
   SAME index with a larger k (such as 8), a different strategy, or a sharper
   reformulated query, and prefer the document that truly contains the answer.

Always put a one-line `rationale` on every search explaining WHY you chose that
index, strategy, k, and wording — this is shown to learners.

When you can answer with grounded evidence, call `finish` with the answer and the
list of sources you used (format "INDEX/doc_id"). If after a genuine effort the
knowledge bases do not contain the answer, say so in `finish`.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search ONE knowledge base with a chosen strategy and k. "
                           "Call it multiple times to search several indexes or to "
                           "issue multiple query variations.",
            "parameters": {
                "type": "object",
                "required": ["index_name", "query_text", "strategy", "k", "rationale"],
                "properties": {
                    "index_name": {
                        "type": "string",
                        "enum": list(INDEXES.keys()),
                        "description": "Which knowledge base to search.",
                    },
                    "query_text": {
                        "type": "string",
                        "description": "The query actually sent to retrieval — either "
                                       "the user's wording, or your rewritten/variant query.",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["bm25", "vector", "hybrid"],
                        "description": "Retrieval strategy for THIS search.",
                    },
                    "k": {
                        "type": "integer",
                        "description": "Number of documents to retrieve (e.g. 3, then 8 if weak).",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "One line: why this index + strategy + k + wording.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Provide the final grounded answer and cite the sources used.",
            "parameters": {
                "type": "object",
                "required": ["answer", "sources_used"],
                "properties": {
                    "answer": {"type": "string", "description": "The answer to the user."},
                    "sources_used": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sources as 'INDEX/doc_id', e.g. 'HR/hr_casual_leave'.",
                    },
                },
            },
        },
    },
]


def _chat(messages, retries=4):
    for attempt in range(retries):
        try:
            return client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
            )
        except Exception as e:
            if ("429" in str(e) or "rate" in str(e).lower()) and attempt < retries - 1:
                time.sleep(2.0 * (2 ** attempt))
                continue
            raise


def _print_tool_call(hop: int, name: str, args: dict, response=None) -> None:
    """Uniform per-hop trace: the tool called, its arguments, and its response."""
    print(f"\n  ┌── HOP {hop}  ·  tool call: {name}")
    print(f"  │   arguments:")
    for key, val in args.items():
        sval = str(val).replace("\n", " ")
        if len(sval) > 110:
            sval = sval[:110] + "…"
        print(f"  │     • {key}: {sval}")
    if name == "finish":
        print(f"  └── tool response: (this call returns the FINAL answer below)")
        return
    if response is None:
        response = []
    print(f"  │   tool response: {len(response)} result(s)")
    for i, h in enumerate(response, 1):
        if isinstance(h, dict) and "error" in h:
            print(f"  │     {i}. ERROR: {h['error']}")
            continue
        idx = h.get("index", "?")
        did = h.get("doc_id", "?")
        score = h.get("score")
        snippet = (h.get("snippet") or "").replace("\n", " ")
        print(f"  │     {i}. {idx}/{did}   (score={score})")
        print(f"  │        “{snippet}”")
    print(f"  └──")


def answer_question(user_query: str, verbose: bool = True) -> dict:
    """Run the agentic RAG loop on one question. Returns a structured trace."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    decisions: list[dict] = []
    step = 0
    hop = 0

    for _ in range(MAX_ITERS):
        resp = _chat(messages)
        msg = resp.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            # Nudge it to use a tool or finish.
            messages.append({
                "role": "user",
                "content": "Use search_knowledge_base to retrieve, or call finish.",
            })
            continue

        finished = None
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            hop += 1

            if tc.function.name == "finish":
                if verbose:
                    _print_tool_call(hop, "finish", args)
                finished = args
                # finish may be batched with searches; handle after loop
                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": "ok",
                })
                continue

            # search_knowledge_base
            step += 1
            index_name = args["index_name"]
            query_text = args["query_text"]
            strategy = args.get("strategy", "hybrid")
            k = int(args.get("k", 3))
            rationale = args.get("rationale", "")

            hits = search(index_name, query_text, strategy=strategy, k=k)
            top_ids = [h.get("doc_id") for h in hits if "doc_id" in h]

            decision = {
                "step": step,
                "index": index_name,
                "strategy": strategy,
                "k": k,
                "query_text": query_text,
                "is_rewrite": query_text.strip().lower() != user_query.strip().lower(),
                "rationale": rationale,
                "num_results": len(top_ids),
                "top_doc_ids": top_ids,
            }
            decisions.append(decision)

            if verbose:
                _print_tool_call(hop, "search_knowledge_base", args, hits)

            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(hits),
            })

        if finished is not None:
            return {
                "user_query": user_query,
                "answer": finished.get("answer", ""),
                "sources_used": finished.get("sources_used", []),
                "decisions": decisions,
                "behaviors": _summarize_behaviors(decisions, user_query),
            }

    # Hit iteration cap — force a finish.
    messages.append({
        "role": "user",
        "content": "You have reached the search limit. Call finish now with your best answer.",
    })
    resp = _chat(messages)
    for tc in (resp.choices[0].message.tool_calls or []):
        if tc.function.name == "finish":
            f = json.loads(tc.function.arguments)
            return {
                "user_query": user_query,
                "answer": f.get("answer", ""),
                "sources_used": f.get("sources_used", []),
                "decisions": decisions,
                "behaviors": _summarize_behaviors(decisions, user_query),
            }
    return {
        "user_query": user_query, "answer": "(no answer)", "sources_used": [],
        "decisions": decisions, "behaviors": _summarize_behaviors(decisions, user_query),
    }


def _summarize_behaviors(decisions: list[dict], user_query: str) -> dict:
    from collections import defaultdict
    indexes = [d["index"] for d in decisions]
    distinct_indexes = list(dict.fromkeys(indexes))

    # multi-query: the agent issued more than one DISTINCT query variation
    # (the user's definition allows variations within an index OR across indexes).
    distinct_queries = {d["query_text"] for d in decisions}
    per_index_queries = defaultdict(set)
    for d in decisions:
        per_index_queries[d["index"]].add(d["query_text"])
    same_index_multi_query = any(len(q) > 1 for q in per_index_queries.values())

    # adaptive-K: a later search re-queried an index with a larger k than before.
    adaptive_k = False
    seen_k = {}
    for d in decisions:
        prev = seen_k.get(d["index"])
        if prev is not None and d["k"] > prev:
            adaptive_k = True
        seen_k[d["index"]] = max(prev or 0, d["k"])

    return {
        "num_searches": len(decisions),
        "indexes_routed": distinct_indexes,
        "fan_out": len(distinct_indexes) > 1,
        "any_rewrite": any(d["is_rewrite"] for d in decisions),
        "multi_query": len(distinct_queries) > 1,
        "same_index_multi_query": same_index_multi_query,
        "strategies_used": list(dict.fromkeys(d["strategy"] for d in decisions)),
        "adaptive_k": adaptive_k,
    }
