# Phase 1 corpus findings (input to Phase 2 extraction)

Recorded 2026-10-02 by inspecting the five saved pages in `data/raw/`.

## Headline

**No headless browser is needed.** All four core fee/benchmark facts are present in real
server-rendered markup, so the `extract.py` design in `architecture.md` §6.2 works as written. The
open question in `architecture.md` §20.2 is resolved.

## Availability of the six core question types

| Category | In visible text? | Evidence |
|----------|------------------|----------|
| Expense ratio | Yes, 5/5 | 1.04% (Large Cap), 0.77% (Equity), 1.21% (ELSS), 0.79% (Small Cap), 0.78% (Balanced Advantage) |
| Exit load | Yes, 5/5 | Definition text present; per-scheme values to be confirmed in P2 |
| Minimum SIP | Yes, 5/5 | `Min. for SIP ₹100` |
| ELSS lock-in | Yes, ELSS only | `Lock-in` label present in ELSS page; duration to be confirmed |
| Benchmark | Yes, 5/5 | Key-value spec list, e.g. `benchmark NIFTY 100 Total Return Index` |
| **Riskometer** | **No, 0/5 in visible text** | See below |

## Two findings that change Phase 2

### 1. Riskometer is not in the rendered text — it is in the embedded JSON payload

Evidence, from `hdfc-large-cap-fund-direct-growth.html`:

```
"nfo_risk":"Moderately High Riskometer"
```

Present in the raw HTML for 3 of 5 pages (Large Cap, Small Cap, Balanced Advantage, value
`Moderately High Riskometer`). ELSS and Equity carry the same value but without the trailing word
`Riskometer`, so a naive keyword match on `riskometer` finds only 3 pages.

**Impact:** PRD acceptance criterion 5 (riskometer/benchmark) cannot be answered from visible text
alone.

**Options for Phase 2 — decide before writing `extract.py`:**
- (a) Mine the `__NEXT_DATA__`-style JSON payload for `nfo_risk` and emit it as a synthetic
  `paragraph` block tagged `category="riskometer"`. Cheap, keeps the data, but the value is
  distributor-reported and unlabelled for 2 pages.
- (b) Treat riskometer as a known corpus gap, state it in the README known-limits section, and
  have the chatbot answer "not in my sources" for it.
- (c) Add official HDFC/SEBI riskometer pages to the corpus in a later phase (addresses PRD R2 as
  well).

Option (a) plus (c) is the strongest position for the demo. This is a human decision.

### 2. Every `<table>` on these pages is a performance table

The four `<table>` elements on the Large Cap page are, in order:

| # | Contents |
|---|----------|
| 0 | Historic returns — "Would've become ₹…" for 1/3/5/10 years |
| 1 | Portfolio holdings — top stocks with weights |
| 2 | Fund returns vs category average and rank (1Y/3Y/5Y/All) |
| 3 | Peer comparison across other Large Cap funds |

None of them is a fee table. Fees live in `<div>` key-value markup, not tables.

**Impact:** this directly threatens the PRD rule "no performance claims" (FR-4.3, R7). Left alone,
these four tables are exactly the kind of dense, high-similarity content that wins top-k for a
generic question like "how did this fund do", and the model would then be answering a performance
question from retrieved context.

**Required Phase 2 behaviour:** treat performance/returns/holdings/peer-comparison tables as
boilerplate and drop them, per the blocklist in `architecture.md` §6.2. Returns also appear in
`<div>` markup (e.g. `3Y annualised +11.29%`), so the blocklist must work on section headings and
text, not only on `<table>` elements. This needs an explicit rule and a regression test in
`tests/test_extract.py`.

## Consequences for later phases

- PRD AC-5 (riskometer) is at risk. Resolve before P11 calibration.
- P2 must emit a per-scheme category coverage report, because coverage is now known to be uneven.
- P5's diversity selection matters more than planned: with returns data removed, a small number of
  fee/benchmark chunks carry the whole corpus.

## Confirmed during Phase 3 (added 2026-10-02)

Both open questions above are now resolved in code, and three further findings appeared while
validating the chunk dump.

**Option (a) was taken for riskometer.** All five pages yield `Moderately High`, via the `nfo_risk`
payload key rather than a keyword match on `riskometer`, so the two ELSS/Equity pages that omit the
trailing word are still covered. PRD AC-5 is answerable from the corpus as it stands.

**Exit load and ELSS lock-in are JSON-only too.** Both appear under an `analysis_subject` key with
values `exit_load` and `lock_in`; only the ELSS page carries lock-in, and its value is `3Y`. These
are whitelisted alongside `nfo_risk`, and comparative entries are rejected so that one scheme's
slab cannot leak into another's answer.

**No `<table>` survives extraction**, as §2 predicted. The atomic-table rule in `architecture.md`
§8.2 therefore has no real input from this corpus and is exercised only by `tests/test_chunker.py`.

**Returns survive outside the removed sections.** `3Y annualised: -0.84 %` and `NAV: 01 Oct '26:
₹1,151.92` live in plain divs, and pairing can split a return row so that neither half matches a
period-and-return pattern. Since no fee, exit load, or tax figure in this corpus is negative, a
negative percentage is now treated as a return. A scan of the final corpus finds no return figure,
NAV, or period toggle; every surviving percentage is a fee, exit load, stamp duty, or tax fact.

**The FAQ sections are client-rendered and absent from the fetched HTML**, so zero `faq_qa` blocks
come from real data. Earlier runs produced two bogus FAQs by pairing navigation items that happened
to end in a question mark; requiring a minimum word count on both the question and the answer
removed them. The pairing code remains covered by synthetic-HTML tests.

**Spec rows must be paired at the innermost container.** The minimum-investments rows live in
`div.minInvestments_table`, which wraps several label/value pairs. Flattening that container shifted
every pair by one field, so `Min. for 1st investment: ₹100` was emitted as
`₹100: Min. for 2nd investment` and the correct orientation never appeared at all — a direct threat
to PRD acceptance criterion 1. Fixed by refusing to flatten an element when a descendant already
pairs cleanly. This was invisible to the synthetic tests and only surfaced by reading the real dump.
