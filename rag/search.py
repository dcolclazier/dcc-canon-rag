"""Search the DCC canon RAG database."""

import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

DB_PATH = Path(os.environ.get("INDEX_DIR", Path(__file__).resolve().parent / "chroma_db"))
COLLECTION_NAME = "dcc_canon"

_client: chromadb.ClientAPI | None = None


def _get_collection():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(DB_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client.get_collection(COLLECTION_NAME)


def search(
    query: str,
    n_results: int = 10,
    domains: list[str] | None = None,
    where: dict[str, Any] | None = None,
) -> list[dict]:
    """Semantic search over the canon corpus.

    Args:
        query: Natural language search query.
        n_results: Max results to return.
        domains: Filter to specific domains (resistance, bestiary, world_spine, etc.).
        where: ChromaDB metadata filter (e.g., {"region": "hackers", "score": {"$gte": 9.5}}).

    Returns:
        List of result dicts with id, text, domain, metadata, distance.
    """
    collection = _get_collection()

    # Build where filter
    filters = {}
    if domains and len(domains) == 1:
        filters["domain"] = domains[0]
    elif domains and len(domains) > 1:
        filters["domain"] = {"$in": domains}

    if where:
        if filters:
            filters = {"$and": [filters, where]}
        else:
            filters = where

    kwargs: dict[str, Any] = {
        "query_texts": [query],
        "n_results": n_results,
    }
    if filters:
        kwargs["where"] = filters

    results = collection.query(**kwargs)

    output = []
    if results and results["ids"]:
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "id": doc_id,
                "text": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })

    return output


def entity_lookup(name: str, domain: str | None = None) -> list[dict]:
    """Search for a specific entity by name."""
    # Use semantic search with the entity name as query
    return search(
        query=name,
        n_results=10,
        domains=[domain] if domain else None,
    )


def list_domains() -> dict:
    """List available domains and chunk counts."""
    collection = _get_collection()
    total = collection.count()

    # Get domain distribution
    all_meta = collection.get(include=["metadatas"])
    domain_counts: dict[str, int] = {}
    for meta in (all_meta["metadatas"] or []):
        d = meta.get("domain", "unknown")
        domain_counts[d] = domain_counts.get(d, 0) + 1

    return {
        "total_chunks": total,
        "domains": domain_counts,
    }
