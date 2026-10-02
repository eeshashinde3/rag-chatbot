# Chunking strategy (Phase 3A proposal)

**Date:** 2026-10-02
**Status:** approved and implemented
**Evidence:** `docs/chunk_analysis.py`, run over the five saved pages in `data/raw/`
**Token counts:** real `all-MiniLM-L6-v2` tokenizer, not a character estimate

This document is the Phase 3A gate deliverable required by `implementation.md`. The values below
were then applied to `src/ragmf/config.py` and implemented in `src/ragmf/ingest/chunk.py`.

---

## 1. Headline: the default strategy in `config.py` is wrong for this data

`architecture.md` §8.2 and `config.py` propose 400-token chunks with 70-token overlap. Measured
against the real corpus, that is roughly 5x too large. Measured block sizes:

| Statistic | Tokens |
|-----------|--------|
| blocks in corpus | 1337 |
| mean | 10 |
| median | 8 |
| p75 | 10 |
| p90 | 15 |
| p99 | 45 |
| max | 146 |
| blocks ≤ 50 tokens | 99.3% |
| blocks ≤ 100 tokens | 99.6% |

The corpus is not prose. It is **~1300 tiny, self-contained spec rows**, most of them 5 to 15 tokens:

```
Expense ratio: 1.04%
Min. for SIP: ₹100
Fund benchmark: NIFTY 100 Total Return Index
Exit load: A fee payable to a mutual fund house for exiting a fund (fully or
partially) before the completion of a specified period from the date of investment.
```

Packing simulation on the Large Cap page (265 blocks):

| max tokens | overlap | chunks | mean size | avg blocks per chunk |
|-----------|---------|--------|-----------|----------------------|
| 400 | 0 | **7** | 357 | **36.3** |
| 150 | 0 | 18 | 139 | 14.1 |
| 100 | 0 | 28 | 89 | 9.1 |
| 80 | 0 | 36 | 69 | 7.1 |
| 60 | 0 | 46 | 54 | 5.5 |

At 400 tokens a chunk would hold **36 unrelated facts** — NAV, expense ratio, fund-manager biography,
AMC address, tax definitions — and the top-ranked chunk's URL would still be right only by accident.
It would also make `show_context` useless to a reviewer, since no chunk is independently answerable.

## 2. Proposed strategy

| Parameter | Value | Was |
|-----------|-------|------|
| `max_tokens` | **90** | 400 |
| `overlap_tokens` | **20** | 70 |
| unit | section-bounded packing of spec rows | section-bounded packing |
| atomic units | spec rows, glossary entries, `faq_qa` | tables, `faq_qa` |

**Why 90.** It holds 6–9 spec rows from one section (simulation: 28–36 chunks per page, mean ~69–89
tokens). Enough surrounding rows that a retrieved chunk reads as a coherent answer to a question,
small enough that MiniLM's 256-token window is never a constraint and that the top-1 chunk's URL is
reliably the correct single citation. It also keeps the whole corpus to roughly 150 chunks, which is
small enough to eyeball in `data/chunks_dump.txt`.

**Why 20, and why only on splits.** With a 10-token mean, a 20-token overlap is roughly two blocks.
Applying overlap between *packed* groups would duplicate facts across chunks and let a duplicate win
top-k, which is worse than no overlap at all for a citation-critical system. Overlap is therefore
applied **only when a single long block must be split**, which affects 5 of 1337 blocks (0.4%).

**Why section-bounded.** Packing never crosses a heading boundary. Without this, a chunk could pair
the exit-load slab table with fund-manager bios, and the "one question, one citation" requirement
stops holding.

**Atomic units that must never be split.** There are **zero** `<table>` blocks in the corpus — every
table on these pages is a returns or holdings table and is dropped as performance data (see
`docs/corpus_findings.md`). The fee and exit-load data lives in spec rows and glossary paragraphs, so
the "tables stay intact" rule from `architecture.md` §8.2 has no table to apply to here. The rule is
retained for future sources, and the atomic-unit concept is applied to `faq_qa` blocks and to
oversized glossary definitions instead.

## 3. What a retrieved fee chunk actually contains

Quoted from the real blocks, packed at `max_tokens=90`:

```
HDFC Large Cap Fund - Direct Growth — Minimum investments
Min. for 1st investment: ₹100
Min. for 2nd investment: ₹100
Min. for SIP: ₹100
```

That is the whole answer to PRD acceptance criterion 1, in one chunk, with one URL. This is the
target shape for every chunk.

## 4. Proposed metadata per chunk

Superset of PRD §8.3. Justification for each added field:

| Field | Source | Why it earns its place |
|-------|--------|-------------------------|
| `chunk_id` | `<source_id>::sec-<n>` | Stable ID; makes `Show sources` and neighbour expansion addressable |
| `source_id` | source registry | Join key to `sources.csv`, so any citation is traceable (AC-18) |
| `scheme` | source registry | Scheme-scoped filtering; prevents Large Cap's fee being cited for Small Cap |
| `category` | `classify_section` | Soft retrieval preference (AD-7) |
| `section_title` | heading path at pack time | Lets the LLM cite a precise section, and a reviewer verify the chunk |
| `plan` | source registry | Prevents Direct/Regular plan conflation (R3) |
| `url` | source registry | The single citation |
| `fetched_at` | source registry | Drives "Last updated from sources" |
| `content_type` | block kind | Distinguishes a spec row from a definition |
| `position` | pack order | **Added.** Neighbour expansion in Phase 5 needs document order; without it a chunk cannot find its neighbours |
| `token_count` | tokenizer | Chunk-size QA and the `≤ max_tokens` test |
| `is_atomic` | packer | **Added.** Flags unsplittable units so a size assertion can exempt them |

`text` is stored in the Chroma document field, not metadata, since Chroma rejects nested metadata.

## 5. Result after implementation

170 chunks over the five pages, all within the limit, byte-identical across runs:

| Metric | Value |
|--------|-------|
| chunks | 170 (33/33/33/33/38) |
| mean | 64 tokens |
| median | 81.5 tokens |
| p90 | 89 tokens |
| max | 90 tokens |
| non-atomic chunks over 90 | 0 |
| unique `chunk_id` | 170/170 |
| `position` contiguous per document | yes |

Every PRD answer target is present in all five schemes: `Min. for SIP`, `Min. for 1st investment`,
`Expense ratio`, `Fund benchmark`, `Riskometer`, `Stamp duty`, exit load, and the redemption-tax
sentence. `Lock-in period: 3Y` appears once, on the ELSS scheme, as expected.

### Two extractor defects found while validating the chunk dump

The dump review surfaced bugs that unit tests on synthetic HTML had not:

1. **Spec rows were being paired one field out of step.** The minimum-investments block sits in
   `div.minInvestments_table`, which contains several `label`/`value` div pairs. Flattening that
   whole container shifted every pair by one, producing
   `Minimum investments: Min. for 1st investment` and `₹100: Min. for 2nd investment`, and the
   correctly-oriented rows were never emitted. Fixed by only treating an element as a spec row when
   no descendant pairs cleanly (`_has_inner_spec_row`). PRD acceptance criterion 1 now resolves from
   `Min. for 1st investment: ₹100`.
2. **Split performance rows survived the performance filters.** `3Y annualised: -0.84 %` sat in divs
   rather than the removed section, and pairing could split it so that neither half matched the
   period-and-return pattern. Since no fee, exit load, or tax figure in this corpus is negative, a
   negative percentage is now treated as a return and dropped, along with `NAV:` prices, bare `1D`
   period toggles, calculator navigation, and orphaned amounts.

A scan of the final corpus confirms **no return figure, NAV, or period toggle remains**, and that
every surviving percentage is a fee, exit load, stamp duty, tax, or lock-in fact.

## 6. Open points for the reviewer

1. **90 tokens, or larger?** If Phase 5 retrieval shows fee chunks are too narrow to carry the
   question's context, 120–150 is the next step. This is a one-line config change.
2. **`category` for spec rows.** Many spec rows classify as `overview` because they are bare
   `label: value` with no heading. Acceptable, but retrieval will lean on scheme filtering.
3. **Glossary definitions.** "Expense ratio", "Exit load", "Stamp duty" appear as short definitional
   paragraphs with no figures. They are useful for "what does X mean?" and useless for "what is the
   X?" — they will compete for top-k. Keeping them is a deliberate trade of precision for coverage.
4. **Zero FAQ blocks.** The FAQ sections on these pages render client-side and do not appear in the
   fetched HTML, so no `faq_qa` chunk exists from real data. The pairing code is still exercised by
   `tests/test_extract.py` and `tests/test_chunker.py` on synthetic HTML. Earlier runs produced two
   fake FAQs built from navigation items; requiring a minimum word count on both sides removed them.
5. **Mild residue.** A few rows keep a date prefix (`08 May 2015: Exit load of 1% if redeemed
   within 1 year`) and some bare spec rows classify as `overview` because they are `label: value`
   with no heading. Both are retrieval-quality concerns for Phase 5, not correctness problems.
