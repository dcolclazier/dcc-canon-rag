"""Convert JSONL/YAML corpus files to individual markdown files for RAG ingestion."""

import json
import os
import yaml
from pathlib import Path

SPARK_ROOT = Path(__file__).resolve().parent.parent
TRUTH = SPARK_ROOT / "training_data_truth"
DATA = SPARK_ROOT / "data"


def convert_bestiary():
    """Extract bestiary_corpus.jsonl → bestiary/entries/*.md"""
    src = TRUTH / "canon" / "bestiary" / "bestiary_corpus.jsonl"
    outdir = TRUTH / "canon" / "bestiary" / "entries"
    outdir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"  Skipping bestiary: {src} not found")
        return 0

    count = 0
    with open(src) as f:
        for line in f:
            d = json.loads(line)
            angle = d.get("angle", f"entry_{count}")
            score = d.get("score", 0)
            phase = d.get("phase", "")
            text = d.get("response", "")

            fname = f"{angle}.md"
            with open(outdir / fname, "w") as out:
                out.write(f"<!-- angle: {angle} | phase: {phase} | score: {score} -->\n\n")
                out.write(text)
            count += 1

    print(f"  Bestiary: {count} entries → {outdir}")
    return count


def convert_achievements():
    """Extract achievements benchmarks.jsonl → achievements/examples/*.md"""
    src = TRUTH / "facility_ai" / "achievements" / "benchmarks.jsonl"
    outdir = TRUTH / "facility_ai" / "achievements" / "examples"
    outdir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"  Skipping achievements: {src} not found")
        return 0

    count = 0
    with open(src) as f:
        for line in f:
            d = json.loads(line)
            convos = d.get("conversations", [])
            if not convos:
                continue

            # Build readable markdown from conversation turns
            parts = []
            for turn in convos:
                role = turn.get("from", "unknown")
                value = turn.get("value", "")
                if role == "system":
                    parts.append(f"**System:**\n{value}")
                elif role == "human":
                    parts.append(f"**Context:**\n{value}")
                elif role == "gpt":
                    parts.append(f"**Response:**\n{value}")

            text = "\n\n---\n\n".join(parts)

            fname = f"achievement_{count:04d}.md"
            with open(outdir / fname, "w") as out:
                out.write(f"<!-- achievement: {count} -->\n\n")
                out.write(text)
            count += 1

    print(f"  Achievements: {count} entries → {outdir}")
    return count


def convert_npc_knowledge():
    """Extract knowledge_corpus.yaml facts → npc/facts/*.md"""
    src = DATA / "npc" / "knowledge_corpus.yaml"
    outdir = DATA / "npc" / "facts"
    outdir.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        print(f"  Skipping NPC knowledge: {src} not found")
        return 0

    with open(src) as f:
        corpus = yaml.safe_load(f)

    if not isinstance(corpus, list):
        # Might be a dict with a top-level key
        if isinstance(corpus, dict):
            for key in ("facts", "knowledge", "entries", "corpus"):
                if key in corpus:
                    corpus = corpus[key]
                    break
            else:
                corpus = list(corpus.values()) if corpus else []

    count = 0
    for item in corpus:
        if isinstance(item, dict):
            text = item.get("text", str(item))
            domains = item.get("domains", [])
            source = item.get("source", "")
            domain_str = ", ".join(domains) if isinstance(domains, list) else str(domains)
        elif isinstance(item, str):
            text = item
            domain_str = ""
            source = ""
        else:
            continue

        fname = f"fact_{count:04d}.md"
        with open(outdir / fname, "w") as out:
            out.write(f"<!-- domains: {domain_str} | source: {source} -->\n\n")
            out.write(text)
        count += 1

    print(f"  NPC knowledge: {count} facts → {outdir}")
    return count


def main():
    print("Converting JSONL/YAML to markdown for RAG ingestion...\n")

    # Resistance stories already converted (stories/*.md)
    stories_dir = TRUTH / "canon" / "resistance" / "stories"
    if stories_dir.exists():
        n = len(list(stories_dir.glob("*.md")))
        print(f"  Resistance: {n} stories already exist at {stories_dir}")
    else:
        print("  Resistance: stories/ not found — run the resistance splitter first")

    convert_bestiary()
    convert_achievements()

    print("\nDone. World Spine files are already markdown — no conversion needed.")
    print("Note: Only training_data_truth/ is indexed. data/ directory is excluded from RAG.")


if __name__ == "__main__":
    main()
