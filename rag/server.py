"""FastAPI server for DCC Canon RAG search."""

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.search import search, entity_lookup, list_domains

_start_time = time.time()
_last_index_time: float | None = None
_indexing = False

# Lazy-loaded SentenceTransformer for the /embed endpoint.
# Chroma uses its own internal ONNX MiniLM-L6-v2 for search; we load a
# sentence-transformers copy here so Node clients (e.g. qwen-memory.ts) have
# one HTTP source of truth for 384-dim all-MiniLM-L6-v2 vectors.
_embed_model: Any = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify DB exists on startup
    try:
        info = list_domains()
        print(f"RAG loaded: {info['total_chunks']} chunks across {len(info['domains'])} domains")
    except Exception as e:
        print(f"Warning: RAG database not found or empty. Run indexer first. ({e})")
    yield


app = FastAPI(title="DCC Canon RAG", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    n_results: int = 10
    domains: list[str] | None = None
    where: dict[str, Any] | None = None


class ReindexRequest(BaseModel):
    domains: list[str] | None = None


class EmbedRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health():
    try:
        info = list_domains()
        return {
            "status": "ok",
            "uptime": time.time() - _start_time,
            "chunks": info["total_chunks"],
            "domains": info["domains"],
            "last_index": _last_index_time,
            "indexing": _indexing,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "uptime": time.time() - _start_time,
        }


@app.post("/search")
def search_endpoint(req: SearchRequest):
    results = search(
        query=req.query,
        n_results=req.n_results,
        domains=req.domains,
        where=req.where,
    )
    return {"results": results, "count": len(results)}


@app.get("/entities")
def entities_endpoint(name: str, domain: str | None = None):
    results = entity_lookup(name, domain)
    return {"results": results, "count": len(results)}


@app.get("/domains")
def domains_endpoint():
    return list_domains()


def _do_reindex(domains: list[str] | None):
    global _last_index_time, _indexing
    _indexing = True
    try:
        from rag.indexer import index_all
        index_all(domains)
        _last_index_time = time.time()
    finally:
        _indexing = False


@app.post("/embed")
def embed_endpoint(req: EmbedRequest):
    """Return 384-dim all-MiniLM-L6-v2 embeddings for each input string.

    Used by the Qwen harness (qwen-memory.ts) so Node has one source of
    truth for embeddings instead of loading a duplicate JS model.
    """
    if not req.texts:
        return {"embeddings": []}
    model = _get_embed_model()
    vectors = model.encode(req.texts, convert_to_numpy=True, normalize_embeddings=False)
    return {"embeddings": [v.tolist() for v in vectors]}


@app.post("/reindex")
def reindex_endpoint(req: ReindexRequest, background_tasks: BackgroundTasks):
    if _indexing:
        return {"status": "already_indexing"}
    background_tasks.add_task(_do_reindex, req.domains)
    return {"status": "started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
