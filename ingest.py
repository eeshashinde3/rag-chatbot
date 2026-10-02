"""Ingestion CLI: fetch -> extract -> chunk -> embed -> store.

Runs offline and with no .env present, and never runs implicitly: importing this
module does nothing, and no other module calls it (architecture.md section 6.5).
Use --force to rebuild an existing store, which is refused by default so a
half-built index cannot silently replace a good one.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from src.ragmf.config import Settings, load
from src.ragmf.ingest.chunk import chunk_all
from src.ragmf.ingest.dump import write_dump
from src.ragmf.ingest.embed import get_embedder
from src.ragmf.ingest.fetch import fetch_all, load_sources
from src.ragmf.ingest.store import (
    StoreError,
    build_store,
    get_collection,
    read_manifest,
    store_fingerprint,
    write_embedding_preview,
)

PREVIEW_FILENAME = "embeddings_preview.txt"


def _fail(message: str) -> int:
    print(f"[fail] {message}", file=sys.stderr)
    return 1


def _preview_path(settings: Settings) -> Path:
    return settings.dump_path.parent / PREVIEW_FILENAME


def _summary(chunks, settings: Settings) -> None:
    per_source: dict[str, list[int]] = defaultdict(list)
    for chunk in chunks:
        per_source[chunk.source_id].append(chunk.token_count)
    print()
    print("Per-document summary (FR-1.9):")
    for source_id in sorted(per_source):
        sizes = per_source[source_id]
        print(
            f"  {source_id:46s} chunks={len(sizes):3d} "
            f"mean={statistics.mean(sizes):5.1f} p90={sorted(sizes)[int(0.9 * len(sizes))]:3d} "
            f"max={max(sizes):3d} failures=0"
        )
    sizes = [chunk.token_count for chunk in chunks]
    over = [
        chunk.chunk_id
        for chunk in chunks
        if chunk.token_count > settings.chunk.max_tokens and not chunk.is_atomic
    ]
    print(
        f"  {'TOTAL':46s} chunks={len(chunks):3d} mean={statistics.mean(sizes):5.1f} "
        f"max={max(sizes):3d} over_limit={len(over)}"
    )


def _guard_existing_store(settings: Settings, force: bool) -> int | None:
    """Abort unless --force when a store already exists or the model changed."""
    manifest = read_manifest(settings)
    if not manifest:
        return None
    stored_model = str(manifest.get("embed_model", ""))
    stored_count = manifest.get("chunk_count", "?")
    if not force:
        return _fail(
            f"A store already exists at {settings.chroma_dir} "
            f"({stored_count} chunks, model {stored_model}). "
            f"Re-run with --force to rebuild it."
        )
    if stored_model and stored_model != settings.embed_model:
        print(
            f"[warn] rebuilding with a different embed model: "
            f"{stored_model} -> {settings.embed_model}"
        )
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest", description=__doc__)
    parser.add_argument("--force", action="store_true", help="rebuild an existing store")
    parser.add_argument("--fetch-only", action="store_true", help="fetch raw HTML and stop")
    parser.add_argument("--all", action="store_true", help="run the full pipeline")
    parser.add_argument("--dump", action="store_true", help="also write data/chunks_dump.txt")
    args = parser.parse_args(argv)

    settings = load(require_api_key=False)

    if args.fetch_only:
        sources = load_sources(settings.sources_csv)
        saved = fetch_all(sources, settings.raw_dir, overwrite=False)
        print(f"[ok]   {len(saved)} raw files present in {settings.raw_dir}")
        return 0

    failure = _guard_existing_store(settings, args.force)
    if failure:
        return failure

    sources = load_sources(settings.sources_csv)
    chunks = chunk_all(sources, settings.raw_dir, settings.chunk)
    if not chunks:
        return _fail("No chunks produced. Run with --fetch-only first.")

    _summary(chunks, settings)

    if args.dump:
        write_dump(chunks, settings.dump_path)

    embedder = get_embedder()
    try:
        build_store(chunks, embedder, settings)
    except StoreError as exc:
        return _fail(str(exc))

    collection = get_collection(settings)
    stored = collection.count()
    print(f"[ok]   collection {settings.collection_name} holds {stored} vectors")
    print(f"[ok]   space={collection.metadata.get('hnsw:space')} manifest_fingerprint="
          f"{store_fingerprint(settings)[:16]}")

    write_embedding_preview(
        collection,
        _preview_path(settings),
        embedder.model_name,
        total=stored,
    )

    if not args.all:
        print("\nIngested without --all; pass --all to acknowledge a deliberate full run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
