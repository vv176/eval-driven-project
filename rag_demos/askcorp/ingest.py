"""
Ingest the AskCorp corpus into its 4 Weaviate collections.

Run (from the eval-driven-project root):
    python -m rag_demos.askcorp.ingest
"""

from rag_demos.askcorp.store import ingest_all, close


def main():
    print("Ingesting AskCorp knowledge bases...")
    ingest_all(reset=True)
    print("Done.")
    close()


if __name__ == "__main__":
    main()
