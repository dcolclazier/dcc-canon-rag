"""Content-type-aware markdown chunking for RAG ingestion."""

import json
import re
from pathlib import Path
from typing import Any


def split_by_headings(text: str, max_chars: int = 2000, overlap: int = 200) -> list[str]:
    """Split markdown by headings, with paragraph fallback for large sections."""
    sections = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) <= max_chars:
            chunks.append(section)
        else:
            # Split large sections by paragraphs
            paragraphs = re.split(r"\n\n+", section)
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 2 > max_chars and current:
                    chunks.append(current.strip())
                    # Overlap: keep last N chars
                    current = current[-overlap:] + "\n\n" + para if overlap else para
                else:
                    current = current + "\n\n" + para if current else para
            if current.strip():
                chunks.append(current.strip())

    return chunks


def parse_md_metadata(text: str) -> dict[str, str]:
    """Extract <!-- key: value | key: value --> metadata from first line."""
    match = re.match(r"^<!--\s*(.+?)\s*-->", text)
    if not match:
        return {}
    meta = {}
    for pair in match.group(1).split("|"):
        if ":" in pair:
            k, v = pair.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def chunk_resistance(stories_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk resistance stories (one .md per region) into search-sized pieces."""
    results = []
    for md_file in sorted(stories_dir.glob("*.md")):
        text = md_file.read_text()
        meta = parse_md_metadata(text)
        region = meta.get("region", md_file.stem)
        score = float(meta.get("score", 0))

        # Remove metadata comment for chunking
        clean = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)
        chunks = split_by_headings(clean, max_chars=2000, overlap=200)

        for i, chunk in enumerate(chunks):
            results.append((chunk, {
                "domain": "resistance",
                "region": region,
                "score": score,
                "source_file": str(md_file.relative_to(stories_dir.parent.parent.parent)),
                "chunk_index": i,
            }))

    return results


def chunk_bestiary(entries_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk bestiary entries (one .md per angle) — whole doc per chunk."""
    results = []
    for md_file in sorted(entries_dir.glob("*.md")):
        text = md_file.read_text()
        meta = parse_md_metadata(text)
        angle = meta.get("angle", md_file.stem)
        score = float(meta.get("score", 0))
        phase = meta.get("phase", "")

        clean = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)
        results.append((clean, {
            "domain": "bestiary",
            "angle": angle,
            "phase": phase,
            "score": score,
            "source_file": str(md_file.relative_to(entries_dir.parent.parent.parent)),
            "chunk_index": 0,
        }))

    return results


def chunk_achievements(examples_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk achievement examples — whole doc per chunk."""
    results = []
    for md_file in sorted(examples_dir.glob("*.md")):
        text = md_file.read_text()
        clean = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)

        results.append((clean, {
            "domain": "achievements",
            "source_file": str(md_file.relative_to(examples_dir.parent.parent.parent)),
            "chunk_index": 0,
        }))

    return results


def chunk_world_spine(spine_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk world spine files (md + yaml) by section."""
    results = []
    for path in sorted(spine_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix not in (".md", ".yaml", ".yml"):
            continue

        text = path.read_text()
        subdomain = path.parent.name if path.parent != spine_dir else "root"
        rel = str(path.relative_to(spine_dir.parent.parent))

        if path.suffix == ".md":
            chunks = split_by_headings(text, max_chars=3000, overlap=200)
        else:
            # YAML: chunk by top-level key
            chunks = _chunk_yaml_by_key(text, max_chars=3000)

        for i, chunk in enumerate(chunks):
            results.append((chunk, {
                "domain": "world_spine",
                "subdomain": subdomain,
                "file_name": path.name,
                "source_file": rel,
                "chunk_index": i,
            }))

    return results


def chunk_npc_facts(facts_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk NPC knowledge facts — one per file."""
    results = []
    for md_file in sorted(facts_dir.glob("*.md")):
        text = md_file.read_text()
        meta = parse_md_metadata(text)
        clean = re.sub(r"^<!--.*?-->\s*", "", text, flags=re.DOTALL)

        results.append((clean, {
            "domain": "npc",
            "fact_domains": meta.get("domains", ""),
            "source": meta.get("source", ""),
            "source_file": md_file.name,
            "chunk_index": 0,
        }))

    return results


def chunk_scoring_guidelines(data_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk scoring guideline markdown files by section."""
    results = []
    for path in sorted(data_dir.rglob("scoring_guideline.md")):
        text = path.read_text()
        target_domain = path.parent.name
        rel = str(path.relative_to(data_dir.parent))

        chunks = split_by_headings(text, max_chars=3000, overlap=200)
        for i, chunk in enumerate(chunks):
            results.append((chunk, {
                "domain": "scoring",
                "target_domain": target_domain,
                "source_file": rel,
                "chunk_index": i,
            }))

    return results


def chunk_npc_yaml(data_npc_dir: Path) -> list[tuple[str, dict[str, Any]]]:
    """Chunk NPC YAML config files (species, roles, scenarios, etc.)."""
    results = []
    skip = {"knowledge_corpus.yaml"}  # Already handled via facts

    for path in sorted(data_npc_dir.glob("*.yaml")):
        if path.name in skip:
            continue

        text = path.read_text()
        chunks = _chunk_yaml_by_key(text, max_chars=3000)

        for i, chunk in enumerate(chunks):
            results.append((chunk, {
                "domain": "npc",
                "subdomain": path.stem,
                "source_file": f"data/npc/{path.name}",
                "chunk_index": i,
            }))

    # Also chunk species subdirectory
    species_dir = data_npc_dir / "species"
    if species_dir.exists():
        for path in sorted(species_dir.glob("*.yaml")):
            text = path.read_text()
            results.append((text, {
                "domain": "npc",
                "subdomain": "species",
                "species": path.stem,
                "source_file": f"data/npc/species/{path.name}",
                "chunk_index": 0,
            }))

    return results


def _chunk_yaml_by_key(text: str, max_chars: int = 3000) -> list[str]:
    """Split YAML text by top-level keys."""
    if len(text) <= max_chars:
        return [text]

    # Split on lines that don't start with whitespace (top-level keys)
    chunks = []
    current = ""
    for line in text.split("\n"):
        if line and not line[0].isspace() and not line.startswith("#") and current:
            if len(current) + len(line) > max_chars:
                chunks.append(current.strip())
                current = line + "\n"
            else:
                current += line + "\n"
        else:
            current += line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks
