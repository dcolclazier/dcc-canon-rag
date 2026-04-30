# dcc-canon-rag

FastAPI vector-search service over the dcc canon corpus. Provides `/search`,
`/entities`, `/embed`, and `/reindex` endpoints. Runs on port 3001 by default.

Extracted from [`dcolclazier/dcc`](https://github.com/dcolclazier/dcc) (originally
at `SPARK/rag/`). See [`docs/adr/0001-extracted-from-dcc.md`](docs/adr/0001-extracted-from-dcc.md)
for the why.

## What it does

- Indexes markdown files under `$CANON_TRUTH_ROOT/canon/`, `$CANON_TRUTH_ROOT/world_spine/`,
  and `$CANON_TRUTH_ROOT/facility_ai/achievements/examples/` into a ChromaDB
  collection (`dcc_canon`).
- Serves semantic search via Chroma's internal MiniLM-L6-v2.
- Exposes a `/embed` endpoint that returns 384-dim `all-MiniLM-L6-v2` vectors,
  used by the agent-middleware's Qwen vector memory.

## Consumers

- **NemoClaw** via the `canon-search` skill — lore lookup mid-conversation.
- **agent-middleware** via `CANON_SEARCH_URL` (Qwen's canon search tool) and
  `RAG_EMBED_URL` (Qwen vector memory writes).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set CANON_TRUTH_ROOT to a path containing canon/, world_spine/, facility_ai/
# (a clone or sparse checkout of dcc).

# Build the index (first run only, or on-demand):
python -m rag.indexer

# Run the server:
uvicorn rag.server:app --host 0.0.0.0 --port 3001
```

## Environment

See [`.env.example`](.env.example).

| Var | Required | Description |
|-----|----------|-------------|
| `CANON_TRUTH_ROOT` | yes | Path to dcc's `SPARK/training_data_truth/` |
| `INDEX_DIR`        | no  | ChromaDB persistence dir (default: `rag/chroma_db`, fine for dev) |
| `PORT`             | no  | HTTP port (default 3001) |

## Operations

- **Reindex**: `POST /reindex` (or run `python -m rag.indexer` manually).
- **Health**: `GET /health` — returns chunk count, indexed domains, uptime.
- **State**: ChromaDB lives at `INDEX_DIR`. Rebuildable from corpus, so no
  backups required.

## License

UNLICENSED — internal use.
