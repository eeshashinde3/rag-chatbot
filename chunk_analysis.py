"""Token statistics over extracted blocks, used to justify the chunking strategy."""

from __future__ import annotations

import statistics
from pathlib import Path

from transformers import AutoTokenizer

from src.ragmf.config import load
from src.ragmf.ingest.extract import classify_section, coverage_report, extract_all
from src.ragmf.ingest.fetch import load_sources
from src.ragmf.models import CATEGORIES, Block

TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
MAX_TOKENS = 256


def count(text: str) -> int:
    return len(TOKENIZER(text, add_special_tokens=False, truncation=True, max_length=MAX_TOKENS)["input_ids"])


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main() -> None:
    settings = load(require_api_key=False)
    blocks_by_source = extract_all(load_sources(settings.sources_csv), settings.raw_dir)

    all_lengths: list[int] = []
    for source_id, blocks in blocks_by_source.items():
        lengths = [count(block.text) for block in blocks]
        all_lengths.extend(lengths)
        tables = [count(b.text) for b in blocks if b.kind == "table"]
        faqs = [count(b.text) for b in blocks if b.kind == "faq_qa"]
        print(f"\n{source_id}")
        print(f"  blocks={len(blocks)}  mean={statistics.mean(lengths):.0f}  "
              f"median={statistics.median(lengths):.0f}  p90={percentile(lengths, 0.9)}  max={max(lengths)}")
        print(f"  tables={len(tables)} longest_table={max(tables) if tables else 0}  faq_qa={len(faqs)}")
        print(f"  under_10_tokens={sum(1 for n in lengths if n < 10)}  under_25_tokens={sum(1 for n in lengths if n < 25)}")

    print("\n=== corpus totals ===")
    print(f"  blocks={len(all_lengths)}  mean={statistics.mean(all_lengths):.0f}  "
          f"median={statistics.median(all_lengths)}  p75={percentile(all_lengths, 0.75)}  "
          f"p90={percentile(all_lengths, 0.9)}  p99={percentile(all_lengths, 0.99)}  max={max(all_lengths)}")
    for bound in (50, 100, 200, 400, 800):
        share = sum(1 for n in all_lengths if n <= bound) / len(all_lengths) * 100
        print(f"  <= {bound:4} tokens: {share:5.1f}% of blocks")

    print("\n=== core-fact neighbours (what a fee chunk must contain) ===")
    large_cap = blocks_by_source["hdfc-large-cap-fund-direct-growth"]
    for index, block in enumerate(large_cap):
        if "Expense ratio" in block.text or "Min. for SIP" in block.text or "Fund benchmark" in block.text:
            start = max(0, index - 3)
            window = large_cap[start:index + 4]
            total = sum(count(b.text) for b in window)
            print(f"\n  anchor: {block.text[:70]}")
            print(f"  +/-3 block window = {total} tokens across {len(window)} blocks")
            for item in window:
                print(f"     [{item.kind:9}] {count(item.text):4}t  {item.text[:72]}")
            break

    print("\n=== category coverage per source ===")
    for source_id, blocks in blocks_by_source.items():
        counts = coverage_report(blocks)
        print(f"  {source_id[:34]:36} " + "  ".join(f"{k}={v}" for k, v in counts.items() if v))

    print("\n=== packing simulation: prose blocks grouped under headings ===")
    for max_tokens in (200, 300, 400, 500):
        for overlap in (0, 40, 70):
            chunks = simulate(blocks_by_source["hdfc-large-cap-fund-direct-growth"], max_tokens, overlap)
            sizes = [c.token_count for c in chunks]
            print(f"  max={max_tokens} overlap={overlap} -> chunks={len(chunks):4} "
                  f"mean={statistics.mean(sizes):.0f} p90={percentile(sizes, 0.9)} max={max(sizes)}")


def simulate(blocks: list[Block], max_tokens: int, overlap: int) -> list:
    from src.ragmf.ingest.chunk import chunk_document
    from src.ragmf.models import SourceRecord

    source = SourceRecord(
        source_id="hdfc-large-cap-fund-direct-growth",
        scheme="HDFC Large Cap Fund - Direct Growth",
        category="overview",
        plan="direct_growth",
        url="https://example.invalid",
        fetched_at="2026-10-02",
        content_type="html",
    )
    from src.ragmf.config import ChunkConfig

    return chunk_document(blocks, source, ChunkConfig(max_tokens=max_tokens, overlap_tokens=overlap))


if __name__ == "__main__":
    main()
