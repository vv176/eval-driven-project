"""
OpenAI embedding helper. Mirrors /Users/vivekanandvivek/RAG/embedder.py.

Returns a vector for a single text or a list of texts using
text-embedding-3-small (1536 dims).
"""

from __future__ import annotations

import os
from typing import List, Sequence

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from openai import OpenAI

_client = None


def _client_singleton() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in environment.")
        _client = OpenAI(api_key=api_key)
    return _client


def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    cleaned = text.replace("\n", " ").strip()
    if not cleaned:
        raise ValueError("text is empty after trimming")
    resp = _client_singleton().embeddings.create(model=model, input=cleaned)
    return resp.data[0].embedding


def get_embeddings(texts: Sequence[str],
                   model: str = "text-embedding-3-small") -> List[List[float]]:
    cleaned = [t.replace("\n", " ").strip() for t in texts]
    if any(not t for t in cleaned):
        raise ValueError("one of the texts is empty after trimming")
    resp = _client_singleton().embeddings.create(model=model, input=cleaned)
    return [d.embedding for d in resp.data]
