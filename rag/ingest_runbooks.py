"""
Embed and ingest data_v2/runbooks/*.md into Weaviate RunbookChunk collection.

Usage:
    python -m rag.ingest_runbooks            # incremental (skip existing)
    python -m rag.ingest_runbooks --reset    # wipe + reingest
"""

from __future__ import annotations

import sys
from pathlib import Path

from rag.chunker import chunk_directory
from rag.embedder import get_embedding
from rag.weaviate_client import (
    insert_chunk, reset_collection, count_chunks, close,
)


def main():
    reset = "--reset" in sys.argv
    runbook_dir = Path(__file__).parent.parent / "data_v2" / "runbooks"

    if reset:
        print("Wiping RunbookChunk collection...")
        reset_collection()

    print(f"Chunking {runbook_dir}...")
    chunks = chunk_directory(runbook_dir)
    print(f"Produced {len(chunks)} chunks from "
          f"{len({c.runbook_file for c in chunks})} runbooks")

    inserted = 0
    skipped = 0
    for i, ch in enumerate(chunks, 1):
        try:
            vec = get_embedding(ch.text)
        except Exception as e:
            print(f"  ! embedding failed for {ch.runbook_file}#{ch.chunk_index}: {e}")
            continue
        uuid = insert_chunk(
            runbook_file=ch.runbook_file,
            runbook_title=ch.runbook_title,
            section_title=ch.section_title,
            chunk_index=ch.chunk_index,
            chunk_text=ch.text,
            vector=vec,
        )
        if uuid:
            inserted += 1
        else:
            skipped += 1
        if i % 10 == 0:
            print(f"  ...{i}/{len(chunks)}")

    print(f"\nInserted: {inserted}, skipped (already present): {skipped}")
    print(f"Total chunks now in collection: {count_chunks()}")
    close()


if __name__ == "__main__":
    main()
