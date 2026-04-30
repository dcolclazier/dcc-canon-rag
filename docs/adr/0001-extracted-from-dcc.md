# ADR-0001: Extract canon-search RAG from `dcolclazier/dcc`

**Status:** Accepted — 2026-04-30
**Source:** `dcolclazier/dcc@ff7c0789` at `SPARK/rag/`

## Context

The canon-search RAG was a Python package under `dcolclazier/dcc/SPARK/rag/`,
imported as `SPARK.rag.*` and invoked as a FastAPI service. Two services
depended on it: NemoClaw's canon-search skill (cross-machine HTTP) and the
agent-middleware (also cross-machine, for both `/search` and `/embed`).

The middleware extraction (see agent-middleware ADR-0001) prompted asking
whether the RAG also belongs in its own repo. Yes:

1. Different stack (Python/FastAPI vs the middleware's Node/TS), different
   reviewers, different deploy lifecycle.
2. The RAG has zero coupling to the SPARK training pipeline — verified that
   nothing under `dcc/SPARK/src/**` imports `SPARK.rag`.
3. Both new services (agent-middleware + this) deploy together to Spark #2
   for reliability; pulling them out of dcc keeps dcc focused on game + canon
   data + training pipeline.

## Decision

Extract `dcc/SPARK/rag/` into `dcolclazier/dcc-canon-rag` as a standalone
Python package named `rag`.

Changes from the source code in dcc:

- Imports rewritten: `from SPARK.rag.X import …` → `from rag.X import …`
  (only intra-package imports — nothing outside the rag/ tree imported it).
- Path constants now env-driven so the service runs from any clone, not just
  from inside dcc:
  - `CANON_TRUTH_ROOT` replaces the hardcoded `__file__.parent.parent / "training_data_truth"`.
  - `INDEX_DIR` replaces the hardcoded `__file__.parent / "chroma_db"`.
- Added `pyproject.toml` for proper packaging.
- ChromaDB persistence path defaults to `rag/chroma_db` for dev convenience but
  is gitignored. Production sets `INDEX_DIR=/var/lib/dcc-canon-rag/chroma_db`.

The corpus itself (`dcc/SPARK/training_data_truth/`) **stays in dcc**. The RAG
is a read-only consumer of those files at runtime via `CANON_TRUTH_ROOT`.

## Alternatives considered

- **Keep in dcc, just relocate to a Spark.** Rejected: doesn't fix the repo
  hygiene problem.
- **Move canon corpus into this repo too.** Rejected: SPARK training pipeline
  in dcc reads canon files, and we don't want to refactor SPARK paths during
  a hosting migration.

## Consequences

**Positive.** The RAG can be deployed to Spark #2 from a small repo that doesn't
require pulling the entire Unity game. The `convert_to_md.py` data-prep script
moves with the indexer (it belongs in the same toolchain), but the canon files
themselves stay where the SPARK pipeline expects them.

**Negative.** The RAG service now needs a path to canon files at runtime
(`CANON_TRUTH_ROOT`). On Spark #2, that path is inside a sparse checkout of dcc
shared with the agent-middleware service. On a developer laptop running this
service for testing, it's the developer's local dcc clone.

## Follow-ups

- ADR-0002 will cover Spark #2 deployment (sparse dcc checkout, systemd unit,
  index rebuild policy).
- `convert_to_md.py` is a data-prep tool that mutates `CANON_TRUTH_ROOT`. It
  inherits the env-driven path config but its place in the long-term toolchain
  is debatable — it might belong back in dcc/SPARK/ as a build script.
