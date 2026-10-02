# PRD — Mutual Fund FAQ Chatbot (Facts-Only RAG Assistant)

**Status:** Draft for class demo milestone
**Version:** 1.0
**Owner:** RAG Chatbot team
**Source brief:** `docs/Problemstatement.txt`

---

## 1. Summary

Build a small Retrieval-Augmented Generation (RAG) chatbot that answers **factual** questions about a
scoped set of mutual fund schemes using **only** publicly available source pages. Every answer must
carry **one citation link**, must be **≤ 3 sentences**, and must refuse opinionated or portfolio
questions with a polite facts-only message plus an educational link.

Out of scope: investment advice, return calculations or comparisons, account servicing, PII intake.

The deliverable is a working prototype (web app or notebook) plus a short demo, for a class
milestone submission.

---

## 2. Problem Statement

Retail users and support/content teams repeatedly ask the same factual questions about mutual fund
schemes — expense ratio, exit load, minimum SIP amount, ELSS lock-in, riskometer level, benchmark,
and how to download statements. The answers live in official public documents (factsheets, KIM/SID,
scheme FAQ pages, fee/charge pages, riskometer and benchmark notes, statement/tax-document guides),
but those documents are long, PDF-heavy, and inconsistently organised.

Searching them manually is slow. Generic chatbots are worse: they hallucinate fee figures, quote stale
data, and frequently drift into advice ("you should buy X"). There is no free, low-risk way to get a
quick, cited, factual answer today.

**We need a chatbot that only says what the official sources say, and always shows where it said it.**

---

## 3. Goals

| # | Goal | Measure |
|---|------|---------|
| G1 | Answer the seven core factual question types accurately | ≥ 90% of the sample Q&A set answered from cited sources |
| G2 | Every answer carries exactly one source link | 100% of grounded answers |
| G3 | Answers are short and readable | ≤ 3 sentences per answer |
| G4 | Advice / portfolio questions are refused, not answered | 100% refusal on the refusal test set |
| G5 | No PII is ever accepted, logged, or stored | 0 PII fields in code, prompts, logs, and DB |
| G6 | Ingestion runs once and persists | Vector store survives restart; re-index is explicit, not automatic |
| G7 | The pipeline is inspectable by a reviewer | All chunks dumped to a readable `.txt` file |

## 4. Non-Goals

- Investment recommendations, suitability assessment, or asset allocation.
- Computing, comparing, or ranking returns / CAGR / SIP projections. If asked, link the official
  factsheet instead.
- Portfolio advice ("Should I buy/sell?", "Is 20% in ELSS right for me?").
- Live NAV, fund performance feeds, or real-time data.
- Scheme recommendation across funds, goal planning, tax filing assistance.
- Multi-user accounts, auth, sessions persistence, analytics dashboards.
- Ingestion of any private, logged-in, or paywalled content.

---

## 5. Users

| User | Need |
|------|------|
| Retail investor comparing schemes | Quick verified facts on fees, loads, SIP, lock-in, risk, benchmark |
| Support / content team | Fast, reusable answers for repetitive MF questions with a citable source |
| Evaluator / instructor | Clear evidence the system is grounded, scoped, and honest about limits |

---

## 6. Scope

### 6.1 AMC and schemes

**AMC: HDFC Mutual Fund.** Scoped to the **Direct – Growth** plan of five schemes (one more than the
required 3–5, giving coverage of every risk category in the brief).

| # | Category | Scheme | Source URL |
|---|----------|--------|-------------|
| 1 | Large Cap | HDFC Large Cap Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth |
| 2 | Flexi Cap | HDFC Equity Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth |
| 3 | ELSS | HDFC ELSS Tax Saver Fund – Direct Plan – Growth | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth |
| 4 | Small Cap | HDFC Small Cap Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-small-cap-fund-direct-growth |
| 5 | Balanced Advantage (Hybrid) | HDFC Balanced Advantage Fund – Direct Growth | https://groww.in/mutual-funds/hdfc-balanced-advantage-fund-direct-growth |

Plan scope note: only the **Direct – Growth** variant is in scope. Regular/Direct-IDCW plan variants
are out of scope and must not be answered, to avoid conflating fee figures across plans.

### 6.2 Source types to collect

Per scheme: scheme overview/factsheet data, KIM/SID-style scheme documents, scheme FAQ pages,
fee & charge pages (expense ratio, exit load, other charges), riskometer and benchmark notes, and
statement / tax-document download guides.

Additional public reference sources permitted: **SEBI** and **AMFI** (e.g. AMFI NAV/factsheet pages) and
official **AMC** pages.

### 6.3 Source policy

- **Public sources only.** No screenshots of app back-ends; no third-party blogs/YouTube/forums as
  answer sources.
- The five URLs above are distributor-hosted (Groww) scheme pages. They are the URLs supplied by the
  brief, so they are in scope. Where a figure can be cross-verified, prefer or corroborate with the
  official AMC/AMFI document and record both in the source list.
- Every ingested page must be reachable without login and must be recorded in `sources.csv`
  (see §12).

### 6.4 Out-of-scope queries (must be refused)

- "Should I buy/sell HDFC Large Cap?"
- "Is HDFC ELSS good for me?" / "Which is better, Large Cap or Small Cap?"
- "How much will my SIP grow to?" / "What is the 5-year CAGR?" / "Compare returns."
- "Which fund has the highest returns?"
- Anything asking for a recommendation, ranking, or suitability call.

---

## 7. Functional Requirements

### FR-1 — Ingestion pipeline (offline, one-time)

| ID | Requirement |
|----|-------------|
| FR-1.1 | Load source pages from disk (pre-fetched saved copies) — no scraping at query time. |
| FR-1.2 | Clean HTML → readable text, preserving headings and table structure (fees/risk/benchmark live in tables). |
| FR-1.3 | Chunk the text per the strategy in §8.2. |
| FR-1.4 | Attach metadata to every chunk (§8.3). |
| FR-1.5 | Embed chunks with `all-MiniLM-L6-v2` (384-dim, local, no API key). |
| FR-1.6 | Persist to ChromaDB on disk so it is not rebuilt on every restart. |
| FR-1.7 | Write **all** chunks to a human-readable `.txt` dump for review. |
| FR-1.8 | Be idempotent and re-runnable via an explicit command (e.g. `python -m ingest`), never implicitly. |
| FR-1.9 | Report per-document chunk counts and any fetch/parse failures on the console. |

### FR-2 — Retrieval pipeline (per query)

| ID | Requirement |
|----|-------------|
| FR-2.1 | Embed the user question with the **same** `all-MiniLM-L6-v2` model. |
| FR-2.2 | Retrieve top-k chunks from ChromaDB, filtered by scheme when a scheme is identified in the question. |
| FR-2.3 | Return chunks with enough surrounding context to answer (retrieve-then-expand if needed). |
| FR-2.4 | Enforce a minimum relevance score; below threshold → "I don't have that in my sources" + educational link. |
| FR-2.5 | Expose the retrieved chunk text, score, scheme, and source URL for debugging. |

### FR-3 — Answer generation

| ID | Requirement |
|----|-------------|
| FR-3.1 | Answer only from the retrieved context. System prompt forbids outside knowledge. |
| FR-3.2 | Every grounded answer includes **exactly one** citation link from the chunk metadata. |
| FR-3.3 | Answer body is **≤ 3 sentences**. |
| FR-3.4 | Append a "Last updated from sources: \<date\>" line. |
| FR-3.5 | If the context does not contain the answer, say so — never fill the gap with model knowledge. |
| FR-3.6 | If a number conflicts across retrieved chunks, surface the conflict and cite the official document rather than picking one. |
| FR-3.7 | Return the raw context to the caller so the UI can offer a "Show sources" view. |

### FR-4 — Refusal & scope enforcement

| ID | Requirement |
|----|-------------|
| FR-4.1 | Classify the query before answering (facts vs. advice/performance/PII). |
| FR-4.2 | Advice / performance / portfolio questions → polite refusal naming the facts-only policy, plus one relevant **educational** link (e.g. SEBI investor-education page). No answer to the underlying ask. |
| FR-4.3 | Performance questions → link the official factsheet instead of quoting or computing returns. |
| FR-4.4 | Refusal message text is defined once and reused by the app and any notebook. |

### FR-5 — PII safety

| ID | Requirement |
|----|-------------|
| FR-5.1 | Never request, echo, or store PAN, Aadhaar, account numbers, OTPs, emails, or phone numbers. |
| FR-5.2 | Detect PII patterns in the input and refuse with a neutral message; **do not echo the matched value** in the reply or logs. |
| FR-5.3 | Log only a redacted query or a hash of it. |
| FR-5.4 | No analytics, no third-party telemetry, no session transcript files. |

### FR-6 — User interface

| ID | Requirement |
|----|-------------|
| FR-6.1 | Welcome line stating what the assistant does and does not do. |
| FR-6.2 | Three clickable example questions, pre-filled from the core categories (fees, ELSS lock-in, statements). |
| FR-6.3 | Persistent disclaimer: **"Facts-only. No investment advice."** visible in the chat area. |
| FR-6.4 | Each answer renders: answer text → citation link → "Last updated from sources: \<date\>" → "Show sources" expander. |
| FR-6.5 | Loading state while retrieval/generation runs; non-blocking. |
| FR-6.6 | Compact: single page, no backend screenshots, no admin panels. |

### FR-7 — Configuration & secrets

| ID | Requirement |
|----|-------------|
| FR-7.1 | `GROQ_API_KEY` loaded from `.env` only. |
| FR-7.2 | `.env` is git-ignored; `.env.example` is committed with placeholder values. |
| FR-7.3 | App fails fast with a clear message when the key is missing. |
| FR-7.4 | Embedding model, chunk params, and top-k are config constants, overridable via env, not hardcoded mid-pipeline. |

---

## 8. Technical Design

### 8.1 Tech stack (fixed by the brief)

| Layer | Choice | Notes |
|-------|--------|-------|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Local, no API key, 384-dim. Same model for chunks and queries. |
| Vector DB | ChromaDB, persisted to disk | Ingestion runs once. |
| LLM | Groq | Key in `.env`, never committed. |
| Orchestration | Python | Ingestion + retrieval as importable modules. |
| UI | Lightweight chat UI over the same modules | App or notebook; whichever is demoed must use this pipeline. |

### 8.2 Chunking strategy (to be validated against real pages before coding)

Proposed, to be confirmed after inspecting the fetched documents — the strategy must be proposed and
justified **before** implementation, per the brief.

- **Unit:** structure-aware, not fixed-offset. Split on page/section boundaries first (scheme
  overview, fees, exit load, riskometer, benchmark, tax/statement guide), then split long sections.
- **Target size:** ~350–450 tokens per chunk.
- **Overlap:** ~60–80 tokens (~15–20%), enough to keep a fee table's header attached to its rows and
  to avoid splitting a definition from its qualifier.
- **Tables kept intact where possible:** fee and riskometer data are tabular; flattening a table row
  into `"Expense ratio: 0.65% | Exit load: 1.0% (12 months)"` preserves meaning far better than
  splitting cells across chunks.
- **Why:** MF documents are short, headed, table-heavy sections. Fixed-size chunking would cut
  label/value pairs apart and bury a fee under a heading from two sections ago. Structure-first
  chunking keeps each chunk independently answerable, which directly serves the "one question, one
  citation" requirement.

### 8.3 Chunk metadata schema

| Field | Type | Purpose |
|-------|------|---------|
| `chunk_id` | str | Stable ID: `<source_id>::sec-<n>` |
| `source_id` | str | Slug of the source document |
| `scheme` | str | Canonical scheme name (or `general`) |
| `category` | str | `overview` / `fees` / `exit_load` / `sip` / `lock_in` / `riskometer` / `benchmark` / `tax_statement` / `faq` |
| `section_title` | str | Heading the chunk came from |
| `plan` | str | `direct_growth` |
| `url` | str | Citation link |
| `fetched_at` | ISO date | Drives "Last updated from sources" |
| `content_type` | str | `table` / `text` / `faq_qa` |
| `text` | str | The chunk body |

### 8.4 Pipeline

```
INGESTION (offline, `python -m ingest`)
  saved source pages
    → extract readable text (headings + tables preserved)
    → structure-aware chunking (§8.2)
    → attach metadata (§8.3)
    → embed with all-MiniLM-L6-v2 (384-dim)
    → persist to ChromaDB (./chroma_db)
    → dump all chunks to data/chunks_dump.txt for inspection

QUERY (`python -m chat` or the UI)
  user question
    → PII check ──(PII)──→ refuse, no echo
    → intent classification ──(advice/performance)──→ refusal + educational link
    → embed question (same model)
    → retrieve top-k from ChromaDB (scheme filter if detected)
    → score gate ──(below threshold)──→ "not in my sources" + link
    → LLM prompt (context-only, ≤3 sentences, 1 citation) ──(Groq)──
    → answer + citation + "Last updated from sources" + source chunks
```

### 8.5 Query-time prompt contract

- Role: factual extraction only. Explicitly: *do not* use outside knowledge, *do not* recommend,
  *do not* compute or compare returns, *do not* ask for or accept personal identifiers.
- Input: the question plus numbered retrieved chunks with scheme, section, and URL.
- Output: a structured reply of `answer` (≤3 sentences), `citation_url`, `sources_date`, `refused`
  (bool), and `show_context` (chunks), so the UI never has to parse prose.

### 8.6 Failure handling

| Failure | Behaviour |
|---------|-----------|
| Missing `GROQ_API_KEY` | Fail fast with setup instructions |
| ChromaDB not built | Detect and instruct to run ingestion; no auto-build |
| Empty / below-threshold retrieval | "I don't have that in my sources" + educational link |
| Groq API error / rate limit | Show a retry message; no fabricated fallback answer |
| Conflicting figures in sources | Surface the conflict, cite the official document |

---

## 9. Non-Functional Requirements

- **Groundedness:** zero uncited factual claims. Any answer without a source chunk is a failure.
- **Latency:** retrieval sub-second; end-to-end answer under ~10s on a demo laptop.
- **Reproducibility:** pinned dependency versions; one documented setup path.
- **Inspectability:** chunk dump committed; retrieval debug view available.
- **Local-first:** embeddings and vector store run locally; only the generation call leaves the
  machine.
- **Privacy:** no PII in code, prompts, logs, or the vector store.
- **Portability:** ingestion and query phases are separately runnable so the demo needs no network for
  retrieval.

---

## 10. UX / Content Requirements

### 10.1 UI copy

- **Welcome line:** "Hi — I answer factual questions about HDFC Mutual Fund schemes from official
  public pages. Every answer includes a source link."
- **Disclaimer (must appear):** "Facts-only. No investment advice."
- **Example questions (3, clickable):**
  1. "What is the expense ratio of the HDFC Large Cap Fund – Direct Growth?"
  2. "What is the lock-in period for HDFC ELSS Tax Saver Fund?"
  3. "How do I download my capital gains statement?"

### 10.2 Refusal copy (single source of truth)

> "I can only share facts from the official pages I've indexed — I don't give investment advice or
> compare returns. For guidance on choosing or reviewing funds, start here: \<educational link\>"

For performance questions, swap the second line for a pointer to the official factsheet.

### 10.3 Answer format

```
<answer, max 3 sentences>
Source: <one link>
Last updated from sources: <date>
[Show sources ▾]
```

---

## 11. Acceptance Criteria

**Grounded answers**
1. "Expense ratio of HDFC Large Cap – Direct Growth?" returns the correct figure with one link.
2. "Exit load?" returns scheme-specific exit load with one link.
3. "Minimum SIP?" returns the minimum SIP amount with one link.
4. "ELSS lock-in?" returns 3 years with one link.
5. "Riskometer / benchmark?" returns the current riskometer level and benchmark with a link.
6. "How do I download a capital gains statement?" returns the step sequence with a link.

**Safety**
7. "Should I buy HDFC Small Cap?" is refused politely with an educational link and no advice.
8. "Which of these has better returns?" is refused and points to the factsheet; no numbers returned.
9. "My PAN is ABCDE1234F" is refused, and `ABCDE1234F` appears nowhere in output or logs.
10. No code path accepts or stores PAN, Aadhaar, account number, OTP, email, or phone.

**Form & limits**
11. Every grounded answer is ≤ 3 sentences and carries exactly one source link.
12. Every answer shows "Last updated from sources: \<date\>".
13. "Facts-only. No investment advice." is visible in the UI.
14. UI shows a welcome line and 3 example questions.

**Pipeline**
15. Chunks are written to a readable `.txt` file and are individually meaningful.
16. ChromaDB persists; a second run does not re-embed unless ingestion is invoked explicitly.
17. Questions and chunks are embedded with the same 384-dim `all-MiniLM-L6-v2` model.
18. Every cited URL is present in `sources.csv` and is publicly reachable without login.

---

## 12. Deliverables

| # | Deliverable | Format / location |
|---|-------------|-------------------|
| D1 | Working prototype | Running app (or notebook) using the §8.4 pipeline |
| D2 | Demo | ≤ 3-minute video, or a hosted prototype link if available |
| D3 | Source list | `sources.csv` — `source_id, scheme, category, url, fetched_at, plan, notes` (5+ URLs) |
| D4 | README | Setup steps, scope (AMC + schemes), architecture, usage, known limits |
| D5 | Sample Q&A | `sample_qa.md` — 5–10 queries with the assistant's answers and links |
| D6 | Disclaimer snippet | Exact text used in the UI, documented in the README |
| D7 | Chunk dump | `data/chunks_dump.txt` — all chunks with metadata, for inspection |
| D8 | This PRD | `PRD.md` |

---

## 13. Milestones

| Phase | Work | Exit criteria |
|-------|------|---------------|
| M0 — Scope & sources | Fix AMC + 5 schemes, fetch and save public pages, write `sources.csv` | All pages saved locally, reachable, no login |
| M1 — Chunking decision | Inspect the data; propose and justify chunk size, overlap, metadata | Strategy written down and approved **before** code |
| M2 — Ingestion | Extract → chunk → embed → ChromaDB → chunk dump | `chunks_dump.txt` readable; persistence verified |
| M3 — Retrieval + LLM | Query embedding, top-k retrieval, Groq answer with one citation | Acceptance criteria 1–6, 11–12 pass |
| M4 — Guardrails | Refusal classification, PII filter, threshold handling | Acceptance criteria 7–10 pass |
| M5 — UI | Welcome line, 3 examples, disclaimer, citations, sources expander | Acceptance criteria 13–14 pass |
| M6 — Docs & demo | README, `sample_qa.md`, source list, ≤3-min video | D1–D8 complete |

---

## 14. Risks & Known Limits

| # | Risk / Limit | Impact | Mitigation |
|---|--------------|--------|-------------|
| R1 | Figures change (expense ratio, exit load) over time | Stale answers | Show "Last updated from sources"; re-run ingestion; never claim a number is current beyond its source date |
| R2 | Given source URLs are distributor-hosted (Groww), not primary AMC documents | Citation authority questioned in review | Cross-check key figures against official AMC/AMFI documents; record both in `sources.csv`; prefer official docs when they conflict |
| R3 | Only Direct–Growth plans in scope | User asks about Regular or IDWC | Refuse and state the scope limit |
| R4 | MiniLM is a small general-purpose embedder; no financial-domain tuning | Weak retrieval on dense fee tables | Structure-aware chunking, category metadata filters, hybrid keyword fallback, top-k tuning |
| R5 | Small corpus (5 schemes) | Overconfident answers on uncovered questions | Relevance threshold + explicit "not in my sources" path |
| R6 | Table-heavy content flattens poorly | Lost label/value pairing | Table-aware extraction; treat table chunks as distinct `content_type` |
| R7 | LLM may still drift into advice or hallucinate numbers | Policy violation | Prompt constraints, refusal classifier, answer-length cap, and manual review of `sample_qa.md` |
| R8 | PDFs (KIM/SID/factsheets) are harder to parse than HTML | Missing or garbled content | Prefer HTML pages; if a PDF is required, verify extracted text against the rendered page |
| R9 | Hindi/regional or OCR'd documents unsupported | Coverage gap | Out of scope for v1; note as a known limit in the README |
| R10 | Groq rate limits during a live demo | Failed demo moment | Pre-warm a small set of cached demo answers; keep a recorded fallback video |

---

## 15. Open Questions

1. Web app or notebook as the primary demo surface? (App recommended — the UI is an explicit
   deliverable.)
2. Are Groww pages acceptable as the cited source, or must citations be AMC/AMFI URLs only?
3. Should KIM/SID/factsheet PDFs be included in the corpus, or is the HTML page set sufficient for
   v1?
4. Target top-k and score threshold for the demo — to be tuned during M3 and recorded in the README.
5. Which educational link to use for refusals (SEBI investor-education vs. AMFI)?

---

## 16. Out of Scope Confirmation

The following are explicitly **not** part of this build: investment advice or recommendations, return
calculation or comparison, portfolio analysis, live NAV or performance data, account or transaction
servicing, PII collection, multi-user auth, production deployment, and any third-party blog or
non-public source.