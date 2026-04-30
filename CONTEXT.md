# Context — dcc-canon-rag

## Glossary

### Canon corpus
Markdown files under `$CANON_TRUTH_ROOT/canon/**` plus `world_spine/` and
`facility_ai/achievements/examples/`. Source-of-truth lives in
`dcolclazier/dcc/SPARK/training_data_truth/`. This service is a read-only
consumer of that corpus.

### Domain
Top-level subdivision of the canon corpus. Current domains:
- `resistance` — resistance stories (`canon/resistance/stories/*.md`)
- `bestiary` — creature entries (`canon/bestiary/entries/*.md`)
- `achievements` — facility achievement examples (`facility_ai/achievements/examples/`)
- `world_spine` — high-level world structure (`world_spine/*.md`)

### Chunk
A unit indexed in ChromaDB. Each markdown file is split by `rag.chunker` into
one or more chunks with metadata (domain, source path, position). Chunk IDs are
deterministic SHA-256 prefixes of `{domain}:{source}:{index}`.

### Index
The ChromaDB persistent store at `$INDEX_DIR` (default `rag/chroma_db`).
Runtime state, rebuildable from corpus. Excluded from the repo.

### Embed endpoint
`POST /embed` returns 384-dim `all-MiniLM-L6-v2` vectors for arbitrary input
strings. The agent-middleware uses this so it doesn't have to load a duplicate
embedding model in Node.

## Topology

```
agent-middleware ──► /embed   ┐
                              ├──► dcc-canon-rag :3001 ──► ChromaDB (INDEX_DIR)
NemoClaw / Qwen ─────► /search┘                       └──► CANON_TRUTH_ROOT (read-only)
```

## Non-goals

- This is not a memory store for agents — that's MemPalace. This is a corpus
  indexer.
- This service does not write to the corpus. Canon mutations happen via
  `agent-middleware`'s canon-commit endpoint, which writes to dcc and triggers
  a reindex.
