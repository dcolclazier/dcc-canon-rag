"""Index markdown corpus into ChromaDB for semantic search."""

import hashlib
import os
import time
from pathlib import Path

import chromadb
from chromadb.config import Settings

from rag.chunker import (
    chunk_achievements,
    chunk_bestiary,
    chunk_resistance,
    chunk_world_spine,
)

# Root of the dcc training_data_truth tree (contains canon/, world_spine/,
# facility_ai/). On Spark #2 this points into a sparse dcc checkout.
TRUTH = Path(os.environ["CANON_TRUTH_ROOT"]) if os.environ.get("CANON_TRUTH_ROOT") \
    else Path(__file__).resolve().parent.parent / "training_data_truth"
DB_PATH = Path(os.environ.get("INDEX_DIR", Path(__file__).resolve().parent / "chroma_db"))

COLLECTION_NAME = "dcc_canon"


def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=str(DB_PATH),
        settings=Settings(anonymized_telemetry=False),
    )


def chunk_id(domain: str, source: str, index: int) -> str:
    """Deterministic chunk ID."""
    raw = f"{domain}:{source}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def index_all(domains: list[str] | None = None):
    """Run full or partial indexing."""
    start = time.time()
    client = get_client()

    # Delete and recreate collection for clean index
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    all_chunks: list[tuple[str, dict]] = []
    target = set(domains) if domains else None

    # Resistance stories
    stories_dir = TRUTH / "canon" / "resistance" / "stories"
    if stories_dir.exists() and (not target or "resistance" in target):
        chunks = chunk_resistance(stories_dir)
        all_chunks.extend(chunks)
        print(f"  Resistance: {len(chunks)} chunks")

    # Bestiary entries
    entries_dir = TRUTH / "canon" / "bestiary" / "entries"
    if entries_dir.exists() and (not target or "bestiary" in target):
        chunks = chunk_bestiary(entries_dir)
        all_chunks.extend(chunks)
        print(f"  Bestiary: {len(chunks)} chunks")

    # Achievements: NOT indexed by default (2026-09-27, the developer's ruling). The old examples came from
    # a pipeline with book-derived few-shots; they are being salvaged into dcc-game's Voice exemplars
    # instead. Only an explicit `achievements` target still indexes them, for inspection.
    examples_dir = TRUTH / "facility_ai" / "achievements" / "examples"
    if examples_dir.exists() and target and "achievements" in target:
        chunks = chunk_achievements(examples_dir)
        all_chunks.extend(chunks)
        print(f"  Achievements: {len(chunks)} chunks")

    # World Spine
    spine_dir = TRUTH / "world_spine"
    if spine_dir.exists() and (not target or "world_spine" in target):
        chunks = chunk_world_spine(spine_dir)
        all_chunks.extend(chunks)
        print(f"  World Spine: {len(chunks)} chunks")

    # Only training_data_truth content — data/ directory is excluded from RAG

    if not all_chunks:
        print("No chunks to index.")
        return 0

    # Batch upsert (ChromaDB handles embedding via default model)
    print(f"\nIndexing {len(all_chunks)} total chunks...")

    batch_size = 200
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        ids = []
        documents = []
        metadatas = []

        for text, meta in batch:
            cid = chunk_id(meta["domain"], meta.get("source_file", ""), meta["chunk_index"])
            ids.append(cid)
            documents.append(text)
            # ChromaDB metadata must be str/int/float/bool
            clean_meta = {}
            for k, v in meta.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                elif isinstance(v, list):
                    clean_meta[k] = ", ".join(str(x) for x in v)
                else:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        print(f"  Indexed {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

    elapsed = time.time() - start
    print(f"\nDone. {len(all_chunks)} chunks indexed in {elapsed:.1f}s")
    print(f"Database at: {DB_PATH}")
    return len(all_chunks)


if __name__ == "__main__":
    import sys
    domains = sys.argv[1:] if len(sys.argv) > 1 else None
    index_all(domains)
