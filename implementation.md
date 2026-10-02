# Implementation Guide — Mutual Fund FAQ Chatbot

**Status:** Ready to execute
**Version:** 1.0
**Drives implementation of:** `PRD.md` v1.0 and `architecture.md` v1.0
**Intended consumer:** an AI coding agent (Cursor, OpenCode, Claude Code) working phase by phase,
plus a human reviewer approving each phase gate.

This document breaks `architecture.md` §19 into executable phases. Each phase has a single goal, an
exact file list, interface contracts, a copy-pasteable agent prompt, a verification command, and
checkable exit criteria. Phases are strictly ordered; each one is independently runnable and
demoable.

---

## How to use this document

1. Set up the repo and `.env` once (Phase 0).
2. Work phases in order. For each phase, paste its **Agent prompt** into the coding agent.
3. Run the phase's **Verification** commands yourself. Do not trust the agent's report.
4. Check **Exit criteria** as a checklist. If any item fails, fix it in this phase — do not carry
   debt forward.
5. At a **Gate**, stop and review before continuing. Gates exist because the work after them is
   expensive to redo.
6. Tick the phase off in `docs/phase_progress.md` (created in Phase 0).

### Rules for the coding agent

These apply to every phase. The agent prompt restates the relevant ones each time.

1. **Read first.** Before writing code, read `PRD.md`, `architecture.md`, and this file. Quote the
   specific section IDs you are implementing (e.g. "implementing `architecture.md` §6.3").
2. **One phase at a time.** Implement only the current phase. Do not create files, functions, or
   abstractions that belong to a later phase, even if you think you will need them.
3. **Follow the contracts literally.** Dataclass fields, function signatures, and constant names in
   this document are fixed. Later phases import them; renaming breaks the build silently.
4. **No new dependencies** beyond the ones listed in the phase. If you need another, stop and ask.
5. **No secrets in code.** Never read `GROQ_API_KEY` except through `config.py`. Never print, log,
   or return it. Never write it to any file.
6. **No PII handling.** Never log a user query verbatim. Only `sha256(query)[:12]` (see Phase 8).
7. **No comments in code.** Let names, types, and structure carry the meaning. Docstrings on public
   functions and modules are fine and expected; `#` commentary inside function bodies is not.
8. **Type hints everywhere.** All function signatures annotated; dataclasses over tuples.
9. **Config values come from `config.py`.** No literals for chunk size, top-k, threshold, or model
   names in pipeline code.
10. **Do not silently swallow errors.** Every `except` either recovers with a defined fallback or
    re-raises. No bare `except:`.
11. **No LLM call in ingestion.** `python -m ingest` must run with no API key and no network.
12. **Report honestly.** If a phase's verification fails, say so and show the output. Do not claim
    success you have not observed.

### Phase map

| Phase | Build | Milestone | Gate? |
|-------|-------|-----------|-------|
| P0 | Scaffolding, config, dataclasses, deps | — | — |
| P1 | Source acquisition → `data/raw/`, `sources.csv` | M0 | — |
| P2 | HTML extraction → block stream | M1 | — |
| P3 | Chunking + chunk dump | M1 | **GATE** |
| P4 | Embedding + ChromaDB store | M2 | — |
| P5 | Retrieval (filters, search, gate, expand) | M3 | — |
| P6 | Guardrails (PII, intent, copy) | M4 | **GATE** |
| P7 | Generation (prompts, Groq client, validators) | M3 | — |
| P8 | Pipeline orchestrator | M3 | — |
| P9 | CLI chat | M3 | — |
| P10 | Streamlit UI | M5 | — |
| P11 | Eval harness + threshold calibration | M6 | **GATE** |
| P12 | Tests (unit + acceptance) | M6 | — |
| P13 | README, sample Q&A, docs | M6 | — |
| P14 | Demo runbook + final review | M6 | **GATE** |

Gates: **P3** (chunking strategy — the brief requires a written proposal *before* code), **P6**
(refusal behaviour), **P11** (threshold calibration), **P14** (submission readiness).

### Conventions

- Python 3.11+, `src/` layout, package name `ragmf`.
- Modules are importable; nothing runs work at import time except lazy singletons
  (`get_embedder()`, `get_client()`).
- Every module has a module-level docstring stating its single responsibility.
- Errors that the UI must handle are return values (the `Answer.kind` envelope), not exceptions.
  Exceptions are for programmer error and unrecoverable failure.
- Pinned versions: **do not hand-write version numbers.** Install, then generate
  `requirements.txt` with `pip freeze > requirements.txt` in Phase 0.

---

## Phase 0 — Scaffolding, config, contracts

**Goal:** create the repository skeleton, dependency set, configuration loader, and the dataclasses
every later phase depends on.

**Milestone:** none. **Depends on:** nothing.

### Files to create

```
requirements.txt          (generated, not hand-written)
.env.example
.gitignore
src/ragmf/__init__.py
src/ragmf/config.py
src/ragmf/models.py
docs/phase_progress.md
data/raw/.gitkeep
tests/.gitkeep
```

### Packages

| Package | Used in |
|---------|---------|
| `chromadb` | P4 |
| `sentence-transformers` | P4 |
| `groq` | P7 |
| `beautifulsoup4`, `lxml` | P1/P2 |
| `python-dotenv` | P0 |
| `streamlit` | P10 |
| `requests` | P1 |
| `pytest` | P12 |

### Contracts

`src/ragmf/config.py`

```python
@dataclass(frozen=True)
class ChunkConfig:
    max_tokens: int
    overlap_tokens: int

@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int
    n_candidates_multiplier: int
    min_similarity: float
    max_sentences: int

@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    embed_model: str
    chroma_dir: Path
    collection_name: str
    chunk: ChunkConfig
    retrieval: RetrievalConfig
    intent_llm_enabled: bool
    debug_retrieval: bool
    raw_dir: Path
    dump_path: Path
    sources_csv: Path

def load(require_api_key: bool = True) -> Settings
```

`src/ragmf/models.py`

```python
SCHEME_SLUGS: dict[str, str]          # alias -> canonical scheme name
CATEGORIES: tuple[str, ...]            # PRD 8.3 category enum
CONTENT_TYPES: tuple[str, ...]         # table | text | faq_qa
PLANS: tuple[str, ...]                 # direct_growth

@dataclass
class SourceRecord:
    source_id: str
    scheme: str
    category: str
    plan: str
    url: str
    fetched_at: str                     # ISO date
    content_type: str
    notes: str = ""

@dataclass
class Block:
    kind: Literal["heading", "paragraph", "list", "table", "faq_qa"]
    text: str
    level: int | None = None
    header: str | None = None           # table header row, for tables

@dataclass
class Chunk:
    chunk_id: str
    source_id: str
    scheme: str
    category: str
    section_title: str
    plan: str
    url: str
    fetched_at: str
    content_type: str
    text: str
    token_count: int
    position: int                       # document order, for neighbour expansion

@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    rank: int
    is_expansion: bool = False

@dataclass
class ChunkView:
    chunk_id: str
    scheme: str
    section_title: str
    url: str
    score: float

AnswerKind = Literal[
    "grounded", "not_in_sources", "refused_advice", "refused_performance",
    "refused_pii", "refused_scope", "error",
]

@dataclass
class Answer:
    kind: AnswerKind
    text: str
    citation_url: str | None = None
    citation_label: str | None = None
    sources_date: str | None = None
    link_kind: Literal["source", "educational", "factsheet", None] = None
    show_context: list[ChunkView] = field(default_factory=list)
    retrieval_scores: list[float] = field(default_factory=list)
    notes: str = ""
```

Canonical scheme strings (used verbatim everywhere — no other spelling is valid):

```python
SCHEMES = (
    "HDFC Large Cap Fund - Direct Growth",
    "HDFC Equity Fund - Direct Growth",
    "HDFC ELSS Tax Saver Fund - Direct Plan - Growth",
    "HDFC Small Cap Fund - Direct Growth",
    "HDFC Balanced Advantage Fund - Direct Growth",
)
```

### Config defaults (`architecture.md` §11)

`GROQ_MODEL=llama-3.3-70b-versatile`, `RAGMF_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2`,
`RAGMF_CHROMA_DIR=./chroma_db`, `RAGMF_COLLECTION=mf_faq`, `RAGMF_CHUNK_MAX_TOKENS=400`,
`RAGMF_CHUNK_OVERLAP_TOKENS=70`, `RAGMF_TOP_K=5`, `RAGMF_MIN_SIMILARITY=0.35`,
`RAGMF_MAX_SENTENCES=3`, `RAGMF_INTENT_LLM=0`, `RAGMF_DEBUG_RETRIEVAL=0`.

`load(require_api_key=False)` must succeed without a key — ingestion phases use this. With
`require_api_key=True`, a missing or placeholder key raises `ConfigError` with the message
`Missing GROQ_API_KEY. Copy .env.example to .env and set your key.`

`.gitignore` must contain: `.env`, `chroma_db/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`.

### Agent prompt

```
Implement Phase 0 of implementation.md in this repo. Read PRD.md, architecture.md, and
implementation.md first; cite the section IDs you follow.

Create only the files listed in Phase 0. Do not create any ingestion, retrieval, generation,
guardrail, or UI code yet.

Requirements:
- src/ragmf/config.py: load() reads .env via python-dotenv, applies every default listed in the
  Phase 0 config table, lets env vars override, and returns a frozen Settings dataclass. Paths are
  resolved to absolute Paths relative to the repo root. Define ConfigError.
- require_api_key=False must work with no .env present. require_api_key=True raises ConfigError
  with the exact message given in implementation.md, and also raises if the value is still the
  .env.example placeholder.
- src/ragmf/models.py: the dataclasses, type aliases, SCHEMES, and the enum tuples exactly as
  specified. No methods beyond field defaults.
- .env.example containing GROQ_API_KEY=your_key_here and a comment stating it must never be committed.
- .gitignore with the listed entries. Confirm .env is ignored.
- docs/phase_progress.md: a markdown checklist with one unchecked line per phase P0..P14.
- Install the packages listed in implementation.md, then generate requirements.txt with
  pip freeze. Do not hand-write version numbers.

Verify: python -c "from src.ragmf.config import load; print(load(require_api_key=False))" succeeds
with no .env present. Then show me the resolved Settings output and confirm .env is git-ignored.

Report the exact verification command you ran and its output.
```

### Verification

```powershell
python -c "from src.ragmf.config import load; s = load(require_api_key=False); print(s.chunk, s.retrieval)"
git check-ignore .env
```

### Exit criteria

- [ ] `load(require_api_key=False)` succeeds with no `.env`; `require_api_key=True` raises `ConfigError`
- [ ] All dataclass fields match the contracts above character-for-character
- [ ] Canonical scheme strings are the only spellings in the repo
- [ ] `requirements.txt` generated by `pip freeze`, not hand-written
- [ ] `.env` confirmed git-ignored; no secret value anywhere in the repo
- [ ] `docs/phase_progress.md` has 15 unchecked phase lines

### Out of scope

Any pipeline logic, any ChromaDB import, any prompt text, any HTML parsing.

---

## Phase 1 — Source acquisition

**Goal:** fetch the five scheme pages (plus cross-check sources) once, save raw HTML locally, and
record every source in `sources.csv`.

**Milestone:** M0. **Depends on:** P0.

### Files to create

```
src/ragmf/ingest/__init__.py
src/ragmf/ingest/fetch.py
data/sources.csv
data/raw/*.html
```

### Contracts

```python
SEED_SOURCES: list[SourceRecord]        # the 5 PRD 6.1 URLs, one SourceRecord each

def fetch_all(sources: list[SourceRecord], raw_dir: Path, overwrite: bool = False) -> list[Path]
def load_sources(sources_csv: Path) -> list[SourceRecord]
def write_sources(sources: list[SourceRecord], sources_csv: Path) -> None
```

### Implementation notes

- Fetch with `requests`, a real `User-Agent`, `timeout=30`, and one retry with backoff on 5xx.
- Save the **raw response body** to `data/raw/<source_id>.html` unchanged. No cleaning happens here.
- Refuse to save any response that redirects to a login page: assert the final URL does not
  contain `login`, `signin`, or `auth`.
- `fetched_at` is today's ISO date, set on the `SourceRecord` and **written into the filename
  metadata sidecar**, not the HTML itself, so re-runs are traceable.
- `--fetch-only` mode on the CLI; default behaviour is to skip files that already exist unless
  `--overwrite` is passed.
- `sources.csv` columns, in this exact order (PRD §12 D3):
  `source_id,scheme,category,plan,url,fetched_at,content_type,notes`
- Log one line per source: `source_id`, HTTP status, bytes saved. Log failures loudly and continue,
  then report the failure count at the end.

**Decide now (architecture.md §20.2):** inspect the saved HTML for a fee/exit-load table. If the
figures only appear inside a JS bundle or a JSON blob, stop and report it — Phase 2 needs a
headless-browser snapshot, and that changes the design of `extract.py`.

### Agent prompt

```
Implement Phase 1 of implementation.md. Read PRD.md section 6 and architecture.md sections 6.1 and
14 before coding.

Create src/ragmf/ingest/__init__.py and src/ragmf/ingest/fetch.py only.

- SEED_SOURCES must contain exactly the five scheme URLs from PRD section 6.1, mapped to the
  canonical scheme strings from models.py, plan "direct_growth", source_id = slugified scheme name.
- fetch_all saves raw bytes unmodified to data/raw/<source_id>.html. No parsing, no cleaning.
- Reject any response that lands on a login/auth URL; report it as a failure.
- write_sources emits the CSV column order given in implementation.md. Round-trip it with
  load_sources.

Then fetch the pages for real and report:
1. HTTP status and byte size for each URL.
2. Whether a fee or exit-load table is present in the saved HTML as real markup, or only inside
   JavaScript/JSON. Quote the specific evidence you looked at.
3. Any page that failed, and why.

If the fee tables are JavaScript-rendered, stop after reporting and do not write extract.py. I need
to decide on a headless-browser snapshot step first.
```

### Verification

```powershell
python -m src.ragmf.ingest.fetch --fetch-only
Get-ChildItem data/raw | Select-Object Name, Length
python -c "from src.ragmf.ingest.fetch import load_sources; print(len(load_sources('data/sources.csv')))"
```

### Exit criteria

- [ ] 5 raw HTML files saved, all non-empty, all public (no login redirect)
- [ ] `sources.csv` has 5+ rows, correct column order, round-trips through `load_sources`
- [ ] `fetched_at` is an ISO date on every row
- [ ] Report states definitively whether fee tables are in real markup or JS-rendered
- [ ] Re-running with existing files does not refetch (idempotent)

### Out of scope

HTML cleaning, chunking, embeddings. Do not create `extract.py`.

---

## Phase 2 — Extraction

**Goal:** turn a saved HTML page into an ordered `Block` stream that preserves headings and tables.

**Milestone:** M1. **Depends on:** P1.

### Files to create

```
src/ragmf/ingest/extract.py
tests/test_extract.py
```

### Contracts

```python
def extract_document(html: str, source: SourceRecord) -> list[Block]
def extract_all(sources: list[SourceRecord], raw_dir: Path) -> dict[str, list[Block]]
def classify_section(heading_path: str, page_text: str) -> str   # -> CATEGORIES value
```

### Implementation notes

1. **Blocklist first.** Remove `script`, `style`, `nav`, `header`, `footer`, `aside`, cookie/consent
   containers, and app-download/promo blocks before anything else. Distributor pages are heavy with
   marketing text that would otherwise dominate retrieval.
2. **Walk in document order.** Collect `h1..h6` → `heading` blocks, `p`/`li` → `paragraph`/`list`,
   `table` → `table`.
3. **Tables.** Capture the header row into `Block.header`. Emit **one `Block` per table**, with rows
   flattened as `label: value | label: value` on separate lines. Never split a table across blocks.
4. **FAQ pairs.** If a heading or a container is followed by a question-like paragraph
   (ends in `?`, or starts with `Q:`/`What`/`How`/`Can`), emit a `faq_qa` block with the question and
   answer lines preserved and prefixed `Q:` / `A:` so the embedder sees the question text.
5. **Heading path.** Maintain the current heading path (`"Fees and charges > Exit load"`) and attach
   it as the context for subsequent blocks. `classify_section` maps the path plus nearby text to one
   of `CATEGORIES` (`overview`, `fees`, `exit_load`, `sip`, `lock_in`, `riskometer`, `benchmark`,
   `tax_statement`, `faq`); default to `overview` when nothing matches. Keyword cues per category are
   listed in `architecture.md` §7.1.
6. **Whitespace.** Normalise runs of whitespace, strip zero-width characters, drop blocks under 25
   characters unless they are headings or table rows.
7. **Determinism.** Same HTML in, identical `Block` list out, every run.

### Agent prompt

```
Implement Phase 2 of implementation.md. Read architecture.md sections 6.2 and 7.1 and PRD
section 8.2 first.

Create src/ragmf/ingest/extract.py and tests/test_extract.py.

Follow the seven implementation notes in Phase 2 exactly. The critical ones: blocklist removal
before extraction, tables emitted as a single Block per table with label: value flattening, and
faq_qa blocks preserving the question text.

classify_section must map a heading path plus surrounding text to exactly one of the CATEGORIES
values from models.py. Use the keyword cues in architecture.md section 7.1 and default to
"overview". Return the category name, not an enum or index.

Tests must cover: a table stays one Block, a heading path is tracked, script/nav content never
appears in output, and a Q:/A: pair becomes one faq_qa block.

Then run extract_all over every file in data/raw and report, per source: block counts by kind, and
for each of the six core categories (fees, exit_load, sip, lock_in, riskometer, tax_statement)
whether at least one block was classified into it. For the five schemes, state plainly which
categories are present and which are missing. A missing category is a corpus gap I need to know
about now, not at demo time.

Show me the verification output.
```

### Verification

```powershell
python -m pytest tests/test_extract.py -q
python -c "from src.ragmf.ingest.extract import extract_all; ..."   # per-source block counts
```

### Exit criteria

- [ ] `test_extract.py` passes
- [ ] No `script`/`nav`/`footer` text in any extracted block
- [ ] Every table is exactly one `Block` with a captured `header`
- [ ] Every block has a non-empty `text`
- [ ] Per-scheme category coverage report delivered; gaps acknowledged
- [ ] Output is deterministic across two runs

### Out of scope

Chunking, embedding, ChromaDB.

---

## Phase 3 — Chunking and chunk dump  ·  GATE

**Goal:** produce inspectable, independently answerable chunks, and write them to
`data/chunks_dump.txt` for human review.

**Milestone:** M1. **Depends on:** P2. **This is a gate** — the brief requires the chunking strategy
to be proposed and justified *before* code is written.

### Phase 3A — Inspect and propose (no code)

Run this before writing `chunk.py`. Produce `docs/chunking_strategy.md` containing:

- What the real data looks like: average block length in tokens, the distribution, how many tables
  per document, longest table in tokens, how often `faq_qa` blocks appear.
- Whether a `fees` section's table and its surrounding prose fit in one 400-token chunk.
- The proposed **chunk size**, **overlap**, and **splitting rule**, with the evidence from *this*
  corpus, not generic best practice.
- The proposed **metadata per chunk** (must be a superset of PRD §8.3) and why each field earns its
  place.
- What a chunk for "expense ratio of HDFC Large Cap Direct Growth" would actually contain — quoted
  from the extracted blocks.

A human must approve this document. The defaults in `config.py` (400 / 70) are placeholders, not
decisions; change them if the data argues for it.

### Files to create

```
docs/chunking_strategy.md              (Phase 3A, human-approved)
src/ragmf/ingest/chunk.py              (Phase 3B)
src/ragmf/ingest/dump.py
tests/test_chunker.py
```

### Contracts

```python
def embed_prefix(chunk: Chunk) -> str      # "<scheme> — <section path>\n"
def count_tokens(text: str) -> int
def chunk_document(blocks: list[Block], source: SourceRecord, cfg: ChunkConfig) -> list[Chunk]
def chunk_all(sources: list[SourceRecord], raw_dir: Path, cfg: ChunkConfig) -> list[Chunk]
def write_dump(chunks: list[Chunk], path: Path) -> None
```

### Algorithm (Phase 3B)

Follow `architecture.md` §6.3 in order:

1. Prepend the context prefix **for embedding only**; `Chunk.text` stays clean.
2. Group blocks under headings, carrying the heading path forward into `section_title`.
3. Emit atomic units: a `table` or `faq_qa` block is one chunk regardless of length.
4. Pack consecutive `paragraph`/`list` blocks up to `max_tokens`; split only over-long units, carrying
   `overlap_tokens` of tail.
5. Assign `chunk_id = f"{source_id}::sec-{n:03d}"` in document order, so `position` is stable and
   neighbours are recoverable.
6. Populate all PRD §8.3 metadata fields plus `token_count` and `position`.

### Dump format (Phase 3B)

Exactly the layout in `architecture.md` §6.6, with a `===...` header per chunk and all metadata
fields shown. This file is a submission deliverable (D7) and will be read by a human.

### Agent prompt (Phase 3A — propose, do not code)

```
Implement Phase 3A of implementation.md. Write docs/chunking_strategy.md only. Do not write any
Python yet.

Extract blocks for all five sources and analyse the real data. The document must contain:
1. Token statistics of the extracted blocks: mean, median, p90, max; block counts by kind; tables
   per document; the longest table in tokens; how many faq_qa blocks appear.
2. Whether a fees section's table plus its surrounding prose fits inside a single 400-token chunk.
3. Your proposed chunk size, overlap, and splitting rule, justified by these specific numbers.
4. The metadata each chunk will carry (must be a superset of PRD section 8.3) and why each field
   earns its place.
5. The exact text of the chunk you expect to retrieve for the question "expense ratio of HDFC
   Large Cap Fund - Direct Growth", quoted from the real extracted blocks.

Then stop. I will review and approve before you write chunk.py.
```

### Agent prompt (Phase 3B — implement, after approval)

```
Implement Phase 3B of implementation.md. I have approved docs/chunking_strategy.md; use the chunk
size, overlap, and metadata from that document, not the placeholders in config.py. If the approved
strategy differs from config.py defaults, update config.py and say so.

Create src/ragmf/ingest/chunk.py, src/ragmf/ingest/dump.py, and tests/test_chunker.py.

Follow the six-step algorithm and the exact dump layout in implementation.md. Tests must cover: no
chunk exceeds max_tokens except a single atomic table; overlap is present between split prose
chunks; chunk_id is stable and sequential; table blocks are never split.

Then run chunk_all over all sources, write the dump, and report:
- total chunk count, mean and p90 chunk size in tokens, chunks per scheme
- the chunk retrieved for "expense ratio of HDFC Large Cap Direct Growth" — print it in full
- any chunk that is under 50 tokens and what it contains
- any table chunk over 500 tokens and whether you think it should be split

Then open data/chunks_dump.txt and quote three chunks verbatim, including one fees chunk and one
riskometer or benchmark chunk, so I can judge whether each chunk is independently answerable.
```

### Verification

```powershell
python -m pytest tests/test_chunker.py -q
python -m src.ragmf.ingest.chunk --all --dump
```

### Exit criteria (Phase 3A)

- [ ] `docs/chunking_strategy.md` exists with all five sections
- [ ] Numbers come from the real corpus, not from generic guidance
- [ ] **Human approval recorded before any code is written**

### Exit criteria (Phase 3B)

- [ ] `test_chunker.py` passes
- [ ] No chunk exceeds `max_tokens` except atomic tables
- [ ] Every chunk is independently answerable (verify three by hand from the dump)
- [ ] Every chunk has all PRD §8.3 metadata fields non-empty except `header`-derived ones
- [ ] `data/chunks_dump.txt` written and readable, one section per chunk
- [ ] Chunking stats reported

### Out of scope

Embeddings, ChromaDB, any network call.

---

## Phase 4 — Embedding and ChromaDB store

**Goal:** embed chunks with MiniLM and persist them to a on-disk ChromaDB collection.

**Milestone:** M2. **Depends on:** P3.

### Files to create

```
src/ragmf/ingest/embed.py
src/ragmf/ingest/store.py
ingest.py                              # CLI entry point
```

### Contracts

```python
def get_embedder() -> Embedder

class Embedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]
    def embed_query(self, text: str) -> list[float]
    model_name: str

def build_store(chunks: list[Chunk], embedder: Embedder, settings: Settings) -> None
def get_collection(settings: Settings) -> chromadb.Collection      # query-time read path
def store_fingerprint(settings: Settings) -> str                   # manifest hash
```

### Implementation notes

- `get_embedder()` is a lazy process-wide singleton. Never instantiate `SentenceTransformer` twice
  in a process — it is the slowest object to construct.
- `embed_documents` embeds `embed_prefix(chunk) + chunk.text`; `embed_query` embeds the raw question.
  Same model, same instance, guaranteed.
- Batch size 64, with a progress line every batch.
- **Chroma setup, exactly as `architecture.md` §6.5 / AD-8:**
  `chromadb.PersistentClient(path=settings.chroma_dir)`;
  `get_or_create_collection(name, metadata={"hnsw:space": "cosine"})`;
  pass `embeddings` explicitly and pass `embedding_function=None`. Chroma must not construct its own
  embedder.
- `ids=[c.chunk_id]`, `documents=[embed_prefix(c) + c.text]`,
  `metadatas=[metadata_without_text]`. **All metadata values must be scalars** — Chroma rejects
  nested or list values. Cast anything to `str`.
- Store a `manifest.json` in `chroma_dir` with the embed model name, chunk count, and a hash of the
  chunk ids. `ingest.py` refuses to rebuild if the manifest's embed model differs from the current
  config, unless `--force` is passed.
- `ingest.py` flags: `--force`, `--fetch-only`, `--all`, `--dump`. Without `--force`, abort if the
  store already exists. **Never auto-ingest on app start.**
- Print the per-document summary required by FR-1.9: chunks, mean size, failures.

### Agent prompt

```
Implement Phase 4 of implementation.md. Read architecture.md sections 6.4, 6.5, 6.6, and AD-8
first.

Create src/ragmf/ingest/embed.py, src/ragmf/ingest/store.py, and the top-level ingest.py CLI.

Non-negotiable: a single lazy SentenceTransformer singleton, embeddings passed explicitly to Chroma,
embedding_function=None, hnsw:space=cosine, and all metadata values coerced to scalars. If Chroma
rejects a metadata field, cast it to str — do not drop the field.

ingest.py must never run implicitly and must never auto-index on import. It must work with no
.env present and no network access.

Then run a full ingest and report:
- chunk count written, collection count read back from disk
- embedding dimensionality of a sample vector (must be 384)
- wall-clock time for embedding
- confirm the collection distance space

Then stop the process, run "python -c" to reopen the collection from a fresh process, and report the
count. If the count is 0 or the collection is missing, the persistence requirement has failed —
report it rather than working around it.
```

### Verification

```powershell
python -m ingest --all --dump
python -c "from src.ragmf.config import load; from src.ragmf.ingest.store import get_collection; print(get_collection(load(require_api_key=False)).count())"
```

### Exit criteria

- [ ] Vectors are 384-dimensional
- [ ] Same `Embedder` instance serves documents and queries
- [ ] Chroma collection uses cosine space and stores our vectors, not a default embedder's
- [ ] All metadata present and scalar-typed; count of chunks written == count read back
- [ ] Store survives a fresh process (verified by a second invocation)
- [ ] `ingest.py` runs with no `.env` and no network
- [ ] `ingest.py` refuses to rebuild without `--force`
- [ ] Manifest records the embedding model name

### Out of scope

Query-time retrieval, prompts, the LLM client.

---

## Phase 5 — Retrieval

**Goal:** embed a question, retrieve the right chunks, gate on relevance, and expand with
neighbours.

**Milestone:** M3. **Depends on:** P4.

### Files to create

```
src/ragmf/retrieval/__init__.py
src/ragmf/retrieval/filters.py
src/ragmf/retrieval/vector_search.py
src/ragmf/retrieval/expand.py
```

### Contracts

```python
@dataclass(frozen=True)
class QueryFilters:
    scheme: str | None
    category: str | None

def detect_filters(question: str) -> QueryFilters
def search(question: str, settings: Settings, filters: QueryFilters) -> list[ScoredChunk]
def expand(chunks: list[ScoredChunk], settings: Settings) -> list[ScoredChunk]
def passes_gate(chunks: list[ScoredChunk], settings: Settings) -> bool
```

### Implementation notes

- `detect_filters` is deterministic string matching, no model. Scheme aliases include
  `"large cap"`, `"largecap"`, `"elss"`, `"tax saver"`, `"small cap"`, `"balanced advantage"`,
  `"flexi cap"`, `"equity fund"`. Two or more distinct schemes matched → `scheme=None`.
- Category hints per `architecture.md` §7.1. If a question matches multiple, take the most specific
  (`exit_load` beats `fees`; `lock_in` beats `overview`).
- `search`: embed the question, query with `n_results = top_k * n_candidates_multiplier`, apply a
  Chroma `where` filter **only** when `filters.scheme` is unambiguous. `score = 1 - distance`.
- **Diversity selection before truncation:** keep the best chunk per `(source_id, category)` pair
  first, then fill remaining slots in score order, so one dense section cannot fill the context and
  hide a contradiction. This is what makes FR-3.6 conflicts visible.
- `passes_gate`: `chunks[0].score >= settings.retrieval.min_similarity`.
- `expand`: for the top-1 chunk only, fetch `position ± 1` within the same `source_id` and append
  with `is_expansion=True`, `rank=len(...)`, so they are excluded from citation candidates.
- Retrieval must not call the LLM and must not write anything.

### Agent prompt

```
Implement Phase 5 of implementation.md. Read architecture.md sections 7.1, 7.2, 7.3, 7.4 and AD-7
first.

Create the four retrieval modules. No LLM calls anywhere in this phase, and no writes to disk.

The two details that matter most: the Chroma where-filter applies ONLY when exactly one scheme is
detected, and diversity selection keeps the best chunk per (source_id, category) before filling
remaining slots in score order.

Then run a retrieval smoke test on these questions and report, for each: detected filters, the
top-5 chunk_ids with scores, and whether it passes the gate at the current threshold of 0.35.
  1. "What is the expense ratio of the HDFC Large Cap Fund - Direct Growth?"
  2. "What is the exit load?"
  3. "What is the lock-in period for HDFC ELSS Tax Saver Fund?"
  4. "How do I download my capital gains statement?"
  5. "Should I buy HDFC Small Cap Fund?"
  6. "What is the weather in Mumbai?"

Questions 1-4 must retrieve the correct scheme and category. Report the raw cosine score
distribution for 1-4 versus 5-6, and tell me whether 0.35 is a sensible gate or whether the two
groups overlap too much to separate with a threshold alone. Do not change the threshold yet; I will
decide that in Phase 11 with a proper evaluation set.
```

### Verification

```powershell
python -m pytest tests/test_retrieval.py -q
```

### Exit criteria

- [ ] Questions 1–4 retrieve the correct scheme and the correct category chunk in the top results
- [ ] Question 5 and 6 do not retrieve fee/load chunks
- [ ] Ambiguous scheme questions fall back to `scheme=None` rather than picking one
- [ ] Diversity selection verified: no single `(source_id, category)` fills more than 2 of 5 slots
- [ ] `expand` marks neighbours with `is_expansion=True` and does not re-rank
- [ ] No LLM call, no disk write in this phase
- [ ] Score distribution for in-scope vs out-of-scope reported

### Out of scope

Prompts, the Groq client, validators, the orchestrator.

---

## Phase 6 — Guardrails  ·  GATE

**Goal:** PII detection, scope and intent classification, and the single source of truth for all
user-facing copy.

**Milestone:** M4. **Depends on:** P5 (independent in practice, ordered for build sanity).

### Files to create

```
src/ragmf/guardrails/__init__.py
src/ragmf/guardrails/pii.py
src/ragmf/guardrails/intent.py
src/ragmf/guardrails/copy.py
tests/test_pii.py
tests/test_intent.py
```

### Contracts

```python
PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...]

@dataclass(frozen=True)
class PIIHit:
    kind: str            # pan | aadhaar | account | otp | email | phone
    start: int
    end: int

def scan_pii(text: str) -> list[PIIHit]
def redact(text: str) -> str
def query_hash(text: str) -> str          # sha256 hexdigest, first 12 chars

Intent = Literal["facts", "advice", "performance", "out_of_scope", "pii"]

def classify_intent(question: str, settings: Settings) -> Intent
```

`copy.py` exports exactly these names — every later phase imports from here, never hardcodes copy:

```python
WELCOME: str
DISCLAIMER: str                  # "Facts-only. No investment advice."
EXAMPLE_QUESTIONS: tuple[str, str, str]
REFUSAL_ADVICE: str
REFUSAL_PERFORMANCE: str
REFUSAL_SCOPE: str
REFUSAL_PII: str
NOT_IN_SOURCES: str
EDUCATIONAL_LINKS: dict[str, str]        # "sebi_investor_education" -> url, "amfi" -> url
FACTSHEET_LINK_TEMPLATE: str              # contains a {url} placeholder
```

Copy must match PRD §10.1 and §10.2 word for word.

### Implementation notes

- **PII patterns** (`architecture.md` §9.1): PAN `[A-Z]{5}[0-9]{4}[A-Z]` with an optional label cue;
  Aadhaar as a 12-digit run with optional separators, gated on a label cue; account number as a
  9–18 digit run adjacent to `a/c`/`account`/`folio`; OTP as a 4–6 digit run adjacent to
  `otp`/`verification code`; email standard; phone Indian mobile with optional `+91`.
  **Label cues are required** for Aadhaar, account, and OTP so that "exit load 1000" and a fee
  figure are not false positives.
- On a hit, the matched value must never appear in the reply, the logs, or the retrieval history.
  `redact` replaces each match with `[redacted:<kind>]`. `query_hash` is the only query identifier
  allowed in logs.
- **Intent order:** `out_of_scope` (plan or scheme outside corpus) → `pii` (if a hit exists) →
  `advice`/`performance` (keyword rules) → optional LLM classifier → `facts`.
- Advice keywords: `should i`, `which is better`, `best`, `worth`, `suggest`, `recommend`, `is it
  good for me`, `my portfolio`, `should I buy`, `sell`.
- Performance keywords: `returns`, `CAGR`, `how much will`, `projection`, `5 year return`, `highest
  return`, `compare performance`, `SIP future value`.
- The LLM classifier runs only when `settings.intent_llm_enabled` is true, only on the question
  text, with no context, three labels, `temperature=0`. On any error it **fails closed** to `advice`.
- Refusals must name the facts-only policy and include one educational link. Performance refusals
  point to the factsheet, per PRD FR-4.3.

### Agent prompt

```
Implement Phase 6 of implementation.md. Read architecture.md section 9 and PRD sections 10.1, 10.2,
and 6.4 first.

Create the three guardrail modules and the two test files. This phase is a gate: refusal behaviour
must be demonstrably correct before we build generation on top of it.

pii.py must be pure pattern matching. No LLM call, ever. Label cues are mandatory for aadhaar,
account, and otp patterns so ordinary numbers in questions are not false positives.

intent.py order is out_of_scope -> pii -> advice/performance keywords -> optional LLM classifier ->
facts. The LLM classifier is off by default and fails closed to advice on any error.

copy.py is the only place user-facing strings exist. Use the exact wording from PRD 10.1 and 10.2.
I will diff your constants against the PRD.

Tests:
- test_pii.py must include the PRD section 11 acceptance string "My PAN is ABCDE1234F" plus an
  assertion that the value does not appear in the refusal or in any log output.
- test_pii.py must also include near-misses that must NOT trigger: "exit load after 1 year",
  "is 3 years the lock-in", "expense ratio 0.65%". Report the false-positive rate on these.
- test_intent.py must cover every refusal example in PRD 6.4 and acceptance criteria 7 and 8, and
  must assert that a list of plain factual questions are NOT refused. Report any false positive on
  the factual list — a refusal on "What is the expense ratio?" is a bug, not a safe default.

Then run both test files and report results plus the two false-positive rates.
```

### Verification

```powershell
python -m pytest tests/test_pii.py tests/test_intent.py -q
```

### Exit criteria (gate)

- [ ] `test_pii.py` and `test_intent.py` pass
- [ ] PRD AC-9 string detected; the PAN value appears in no output and no log
- [ ] Zero false positives on the near-miss numeric questions
- [ ] Zero false positives on the plain factual question list
- [ ] Every PRD §6.4 refusal example classified as `advice` or `performance`
- [ ] All copy constants match PRD §10.1/§10.2 exactly
- [ ] LLM classifier disabled by default; fails closed when enabled and erroring

### Out of scope

Prompts for grounded answers, the Groq client, the orchestrator, the UI.

---

## Phase 7 — Generation and validators

**Goal:** build the prompt, call Groq, and validate the response deterministically.

**Milestone:** M3. **Depends on:** P5, P6.

### Files to create

```
src/ragmf/generation/__init__.py
src/ragmf/generation/prompts.py
src/ragmf/generation/groq_client.py
src/ragmf/generation/answer.py
tests/test_validators.py
```

### Contracts

```python
SYSTEM_PROMPT_V1: str
ANSWER_SCHEMA: dict                          # Groq JSON-schema response format

def build_user_prompt(question: str, chunks: list[ScoredChunk]) -> str
def allowed_urls(chunks: list[ScoredChunk]) -> list[str]

class GroqClient:
    def generate(self, question: str, chunks: list[ScoredChunk]) -> dict
    def classify_intent(self, question: str) -> str

def validate_response(
    raw: dict,
    chunks: list[ScoredChunk],
    settings: Settings,
) -> Answer
```

### Implementation notes

- **Prompt** (`architecture.md` §8.1): role is factual extraction only. Forbid outside knowledge,
  recommendations, return comparison or projection, and requests for or repetition of PAN, Aadhaar,
  account numbers, OTPs, emails, or phone numbers. Cap at 3 sentences. Choose exactly one
  `source_url` from the allowed list. Context blocks are numbered and tagged
  `[scheme | category | source_url | content_type]`. Expanded chunks are labelled so the model treats
  them as background.
- **Schema** returns `answer`, `source_url`, `grounded`, `conflict`, `incomplete`. Use Groq's
  structured-output/JSON-schema mode.
- **Client:** `temperature=0`, low `max_tokens`, one retry with backoff on 429/5xx, second failure
  returns a structured error dict. **Never** falls back to a model-written answer. Read the key from
  `settings`, never from `os.environ` directly, and never log it.
- **Validators**, in this order (`architecture.md` §8.2):
  1. `grounded is False` → `not_in_sources` + educational link
  2. `source_url` not in `allowed_urls` → substitute the top-1 ranked chunk's URL, note it
  3. any other `http` in `answer` → strip, keep the allowed one
  4. sentence count > 3 → truncate at 3
  5. **numeric grounding** — every number-with-unit token in the answer must appear in the context
     text after normalising whitespace, `%`, `,`, and case; strip ungrounded numbers; if the answer
     is left meaningless, return `not_in_sources`
  6. `conflict` non-empty → append the conflict note and force the citation to the official-document
     URL
  7. advice leakage scan (`recommend`, `suggest`, `you should`, `must buy`, `ideal for you`) →
     replace with the refusal template
  8. `sources_date` = max `fetched_at` across **cited** chunks only
- `validate_response` must be pure: same input, same output, no network. It is the unit under test in
  `test_validators.py`, with hand-built dicts covering every rule.

### Agent prompt

```
Implement Phase 7 of implementation.md. Read architecture.md sections 8.1, 8.2, 8.3, 8.4 and
AD-1, AD-2, AD-12 first.

Create the four generation modules and tests/test_validators.py.

The validators are the important part of this phase. Implement all eight checks in the order given
in implementation.md, and make validate_response a pure function with no network access.

The numeric-grounding check must handle "0.65%", "0.65 %", "65 bps", "1.0%", "3 years", and
"12 months" correctly, must not fire on the question's own restated figures when they appear in
context, and must strip rather than hallucinate. Test it against at least six cases: grounded,
ungrounded, mixed, all-stripped, formatting-variant, and a number that is a substring of a longer
one (e.g. "1" inside "10" must not count as grounded).

test_validators.py must cover every one of the eight rules with hand-built response dicts and
assert the exact resulting Answer.kind and citation_url.

Then, using the retrieval results from Phase 5, make three real Groq calls for the questions
"What is the expense ratio of the HDFC Large Cap Fund - Direct Growth?", "What is the exit load?",
and "What is the lock-in period for HDFC ELSS Tax Saver Fund?". For each, report the raw model
JSON, the validated Answer, and which validators fired. Quote the answer text verbatim.
```

### Verification

```powershell
python -m pytest tests/test_validators.py -q
```

### Exit criteria

- [ ] `test_validators.py` passes with all eight rules covered
- [ ] `validate_response` is pure and offline-testable
- [ ] A hallucinated URL is always replaced by a retrieved one
- [ ] A hallucinated number is stripped or escalated, never rendered
- [ ] Three real Grounded answers each have exactly one valid citation and ≤ 3 sentences
- [ ] Groq error path returns an error dict after one retry; no fabricated fallback
- [ ] API key never appears in any log line

### Out of scope

The orchestrator, CLI, UI.

---

## Phase 8 — Pipeline orchestrator

**Goal:** wire every stage into `ragmf.pipeline.ask()` returning the single `Answer` envelope.

**Milestone:** M3. **Depends on:** P5, P6, P7.

### Files to create

```
src/ragmf/pipeline.py
tests/test_pipeline.py
```

### Contract

```python
def ask(question: str, settings: Settings | None = None) -> Answer
```

### Implementation notes

- Execute the eleven steps of `architecture.md` §5 **in that exact order**. The ordering is the
  safety property: PII, scope, and intent all run before anything is embedded, sent, or logged.
- Preflight: store exists, and with `require_api_key=True` the key is valid. On preflight failure
  return `kind="error"` with an actionable message; do not attempt retrieval.
- Log only `query_hash(question)`, the intent, the top score, and the latency. Never the query text,
  never the API key, never a PII value.
- On any unexpected exception in retrieval or generation, return `kind="error"` — never an
  unhandled traceback to the user, and never a fabricated answer.
- This is the only module permitted to import across packages.

### Agent prompt

```
Implement Phase 8 of implementation.md. Read architecture.md section 5 first.

Create src/ragmf/pipeline.py with ask(question, settings=None) -> Answer, implementing the eleven
steps in the documented order. pipeline.py is the only module allowed to import across packages.

Then exercise the full path with these twelve questions and report a table: question, Answer.kind,
citation_url, sources_date, top retrieval score, latency in ms.

  1. What is the expense ratio of the HDFC Large Cap Fund - Direct Growth?
  2. What is the exit load for HDFC Small Cap Fund - Direct Growth?
  3. What is the minimum SIP for HDFC Equity Fund - Direct Growth?
  4. What is the lock-in period for HDFC ELSS Tax Saver Fund?
  5. What is the current riskometer level of HDFC Balanced Advantage Fund?
  6. What is the benchmark of HDFC Large Cap Fund - Direct Growth?
  7. How do I download my capital gains statement?
  8. Should I buy HDFC Small Cap Fund?
  9. Which of these funds has better returns?
  10. What is the expense ratio of the HDFC Large Cap Regular Plan?
  11. My PAN is ABCDE1234F
  12. What is the current NAV of HDFC Large Cap Fund?

Expected kinds: 1-7 grounded, 8 advice, 9 performance, 10 out_of_scope, 11 pii, 12 not_in_sources.
If any of 1-7 is not grounded, report the retrieval scores and the retrieved chunk text so we can
decide whether the problem is chunking, retrieval, or the prompt. If 12 is grounded, that is a
serious failure — report it prominently and tell me what the answer said.
```

### Verification

```powershell
python -m pytest tests/test_pipeline.py -q
```

### Exit criteria

- [ ] All twelve questions return the expected `Answer.kind`
- [ ] Questions 1–7 each carry exactly one valid citation URL and a `sources_date`
- [ ] Refusals return an educational or factsheet link and no answer to the underlying ask
- [ ] Question 11's PAN value appears nowhere in the returned `Answer` or in logs
- [ ] Logs contain query hashes only
- [ ] Preflight failure returns `error` without attempting retrieval

### Out of scope

CLI, UI, evaluation harness.

---

## Phase 9 — CLI chat

**Goal:** a terminal chat interface over `ask()` for fast iteration and for the demo fallback.

**Milestone:** M3. **Depends on:** P8.

### Files to create

```
chat.py
```

### Implementation notes

- On start: load settings, verify the store exists, print `WELCOME`, `DISCLAIMER`, and the three
  `EXAMPLE_QUESTIONS` numbered 1–3.
- Loop: accept `1`/`2`/`3` as example shortcuts, otherwise read free text. `/exit` quits.
- Render every answer in the PRD §10.3 format: text, `Source: <url>`, `Last updated from sources:
  <date>`, then the top retrieved chunk's section and scheme when `RAGMF_DEBUG_RETRIEVAL=1`.
- Never echo the raw question back in a log file. Terminal echo is fine; file logging is not.
- EOF on stdin must exit cleanly.

### Agent prompt

```
Implement Phase 9 of implementation.md: chat.py, a CLI over ragmf.pipeline.ask.

Read PRD section 10.3 for the exact render format. Import all user-facing strings from
guardrails.copy — do not hardcode any text.

Then demo it with six questions, including one factual, one advice, one out-of-scope, and the PAN
one, and paste the terminal output verbatim so I can see the formatting.
```

### Verification

```powershell
python -m chat
```

### Exit criteria

- [ ] Welcome line, disclaimer, and 3 examples print on start
- [ ] `1`/`2`/`3` submit the example questions
- [ ] Output format matches PRD §10.3 exactly
- [ ] No file is written during a session
- [ ] Ctrl-D exits cleanly

### Out of scope

Streamlit UI, evaluation harness.

---

## Phase 10 — Streamlit UI

**Goal:** the single-page chat UI required by PRD FR-6.

**Milestone:** M5. **Depends on:** P8.

### Files to create

```
app.py
```

### Implementation notes

- `st.set_page_config(page_title="MF Facts Assistant", layout="centered")` first.
- All copy from `guardrails.copy`. Do not hardcode strings, including the disclaimer.
- Layout order: welcome line → message history → `st.spinner` while `ask()` runs →
  **disclaimer pinned directly above the input**, always visible → `st.chat_input`.
- Message rendering:
  - `grounded`: `st.write(answer.text)`, then `Source: [label](citation_url)` as a single markdown
    link, then `Last updated from sources: <date>` in small text, then a
    `st.expander("Show sources")` listing each `ChunkView` with scheme, section, and score.
  - refusal kinds: `st.write(answer.text)` with the link rendered the same way; **no** sources
    expander, since nothing was cited.
  - `error`: `st.warning`.
- `st.session_state` holds the message list for the browser session only. Nothing is written to disk.
- **The API key is never referenced in this file.** `ask()` owns configuration; the UI never calls
  `load()` with `require_api_key=True` and never reads `os.environ`.
- No backend admin panels, no debug panels unless gated behind `RAGMF_DEBUG_RETRIEVAL`.

### Agent prompt

```
Implement Phase 10 of implementation.md: app.py, the Streamlit UI. Read PRD section 10 and
architecture.md section 10 first.

Every user-facing string must be imported from ragmf.guardrails.copy. Do not hardcode the welcome
line, the disclaimer, the example questions, or any refusal text.

The API key must never be read or referenced in app.py — ask() owns configuration.

Render grounded answers as: text, a single markdown "Source:" link, "Last updated from sources:",
and a "Show sources" expander. Render refusals as text plus their educational link, with no sources
expander.

Then run the app, screenshot the three states (grounded answer with sources expanded, advice
refusal, not-in-sources), and describe what you see. Confirm the disclaimer is visible in all
three.
```

### Verification

```powershell
python -m streamlit run app.py
```

### Exit criteria

- [ ] Welcome line, disclaimer, and 3 clickable examples render on load
- [ ] Disclaimer visible in every state
- [ ] Grounded answer shows one link, the date, and a working sources expander
- [ ] Refusals show the educational link and no sources expander
- [ ] `app.py` contains no reference to the API key or `os.environ`
- [ ] No file is written during use

### Out of scope

Evaluation harness, tests, docs.

---

## Phase 11 — Evaluation harness and threshold calibration  ·  GATE

**Goal:** build the measurement instrument, calibrate the relevance threshold on evidence, and
generate `data/sample_qa.md`.

**Milestone:** M6. **Depends on:** P8. **Gate** — do not proceed to submission docs without this.

### Files to create

```
src/ragmf/eval/__init__.py
src/ragmf/eval/harness.py
data/sample_qa.md
docs/threshold_calibration.md
```

### Evaluation set

Author these by hand before running anything. They are the whole point of the phase.

- **In-scope (≥ 12):** the six core categories from PRD §11 AC 1–6, each asked about at least two
  different schemes, plus at least four natural phrasings of the same question ("what does it cost
  to hold", "is there a load if I redeem early", "how long is the money stuck").
- **Out-of-scope (≥ 10):** the four PRD §6.4 advice/performance questions, plus non-corpus schemes
  ("What is the expense ratio of a Parag Parag Flexi Cap?"), plus non-MF questions ("Who is the CEO
  of HDFC AMC?", "What is the repo rate?"), plus questions about metrics we deliberately exclude
  ("What is the Sharpe ratio of HDFC Large Cap?").

### Implementation notes

- `harness.py` runs the set through `ask()` and reports: grounded rate on in-scope, rejection rate
  on out-of-scope, refusal rate on the advice set, mean latency, mean top-1 score, and per-question
  rows.
- **Calibration:** sweep `RAGMF_MIN_SIMILARITY` across `0.20 … 0.50` in `0.025` steps. For each
  value report in-scope grounded rate and out-of-scope rejection rate. Choose the value with **zero
  in-scope misses** and the highest out-of-scope rejection. Write the result and the trade-off curve
  to `docs/threshold_calibration.md`, and update `config.py`'s default to the chosen value.
- If no single threshold gives zero in-scope misses, **do not lower the bar** — report the conflict
  and let the human decide between a lower threshold and a chunking fix.
- `data/sample_qa.md` is generated by the harness with columns `query | kind | answer |
  citation_url | sources_date | notes`, covering 5–10 queries, then **hand-reviewed** by a human.
  The review is the deliverable, not the generation.

### Agent prompt

```
Implement Phase 11 of implementation.md. Read architecture.md sections 15 and 20, and PRD
section 11.

First author the evaluation sets yourself as plain lists in the harness: at least 12 in-scope
questions covering all six core categories across at least two schemes each, including natural
phrasings; and at least 10 out-of-scope questions including the four PRD 6.4 advice/performance
ones, non-corpus schemes, non-MF questions, and deliberately excluded metrics.

Then run the baseline at the current threshold and report the full results table.

Then sweep RAGMF_MIN_SIMILARITY from 0.20 to 0.50 in 0.025 steps and report a table of in-scope
grounded rate against out-of-scope rejection rate per threshold. Recommend one value: the highest
threshold with zero in-scope misses. Write the table and your reasoning to
docs/threshold_calibration.md and update the config.py default.

If no threshold achieves zero in-scope misses, STOP and report the conflict with the two curves. Do
not lower the bar and do not proceed.

Finally generate data/sample_qa.md from the harness for 8 representative queries. Do not
hand-write the answers — I will hand-review them, which is the point of the review.
```

### Verification

```powershell
python -m src.ragmf.eval.harness --run
python -m src.ragmf.eval.harness --sweep
```

### Exit criteria (gate)

- [ ] ≥ 12 in-scope and ≥ 10 out-of-scope questions defined
- [ ] Sweep table written to `docs/threshold_calibration.md`
- [ ] Chosen threshold gives **zero in-scope misses**
- [ ] `config.py` default updated to the chosen value
- [ ] Baseline in-scope grounded rate ≥ 90% (PRD goal G1)
- [ ] Advice/performance refusal rate = 100% (PRD AC 7, 8)
- [ ] `data/sample_qa.md` generated with 8 rows and all columns populated
- [ ] `docs/threshold_calibration.md` states the trade-off, not just the number

### Out of scope

Changing prompts or chunking to chase the numbers. If the numbers are bad, report it; a fix is a
new, separately reviewed phase.

---

## Phase 12 — Tests

**Goal:** lock in the acceptance criteria as automated tests.

**Milestone:** M6. **Depends on:** P11.

### Files to create

```
tests/conftest.py
tests/test_acceptance.py
tests/test_end_to_end.py
```

### Implementation notes

- `conftest.py` provides a session-scoped fixture that loads settings, checks the store exists, and
  skips with an actionable message if `python -m ingest` has not been run.
- `test_acceptance.py` encodes PRD §11 criteria 1–14 as individual named tests, using
  `parametrize` for the per-scheme variants. Name each test after the criterion, e.g.
  `test_ac01_expense_ratio_large_cap`.
- `test_end_to_end.py` runs the full ingestion-to-answer path on a temporary store built from
  `data/raw/`, proving the pipeline works from a clean state.
- `test_validators.py` (Phase 7) and the Phase 2/3/6 tests already exist; do not rewrite them.

### Agent prompt

```
Implement Phase 12 of implementation.md. Read PRD section 11 first.

Create tests/conftest.py, tests/test_acceptance.py, and tests/test_end_to_end.py. Encode PRD
acceptance criteria 1 through 14 as individually named tests, parametrised where a criterion applies
to more than one scheme. Do not modify the test files written in earlier phases.

test_end_to_end.py must build a temporary ChromaDB store from data/raw/ in a tmp_path, run
ingestion, then answer at least three questions against it. This proves a reviewer can reproduce
the build from source.

Run the full suite and report the pass count, plus the runtime of the slowest test. If the
acceptance suite is slow because of repeated real LLM calls, mark the LLM-dependent tests with a
marker and register a "slow" marker in pyproject or pytest.ini — but do not skip them by default.
```

### Verification

```powershell
python -m pytest -q
python -m pytest -m "not slow" -q
```

### Exit criteria

- [ ] Full suite passes
- [ ] All 14 PRD acceptance criteria have a named test
- [ ] `test_end_to_end.py` builds a store from `data/raw/` in a tmp dir and answers correctly
- [ ] Suite skips with an actionable message when the store is missing
- [ ] No test asserts on LLM prose wording, only on structure, kind, citation validity, and length

### Out of scope

README, demo.

---

## Phase 13 — Documentation deliverables

**Goal:** produce the submission artifacts.

**Milestone:** M6. **Depends on:** P12.

### Files to create

```
README.md
docs/architecture.md -> architecture.md (already at repo root; link it)
docs/decisions_log.md
```

### Implementation notes

- `README.md`: setup steps (venv, `pip install -r requirements.txt`, `.env`, `python -m ingest`,
  `python -m chat`, `python -m streamlit run app.py`), scope (AMC + 5 schemes, Direct-Growth only),
  architecture summary with a link to `architecture.md`, the calibrated threshold and why, the
  refusal and disclaimer copy verbatim, the test command, and **known limits** (Draw from PRD §14
  risks that are still true, plus: distributor-hosted citations, Direct-Growth only, no PDF parsing
  in v1, no hybrid retrieval, no Hindi/regional sources).
- `docs/decisions_log.md`: the twelve ADRs from `architecture.md` §17 plus the threshold decision
  from Phase 11, each with context and consequence.
- The disclaimer snippet deliverable (D6) must be copied verbatim from `guardrails/copy.py`, and a
  test must assert they match.

### Agent prompt

```
Implement Phase 13 of implementation.md.

Create README.md and docs/decisions_log.md. Read PRD section 12 deliverables and section 14 risks.

README.md must contain: setup steps that actually work in a fresh clone, the scope (HDFC AMC, five
schemes, Direct-Growth plans only), a short architecture summary linking architecture.md, the
calibrated similarity threshold from docs/threshold_calibration.md with the reason it was chosen,
the disclaimer and refusal copy verbatim, how to run tests, and a known-limits section.

Write the known-limits section from what is actually true of the build — read the code and the
Phase 11 results rather than copying PRD risks wholesale. A limit that is no longer true should not
be listed, and a real limitation you find that is not in the PRD should be.

docs/decisions_log.md: the twelve ADRs plus the threshold calibration decision, each with context
and consequence.

Do not invent features or numbers. If a value is not in the repo, leave it out and tell me what is
missing.
```

### Verification

```powershell
python -m pytest -q
```

### Exit criteria

- [ ] A fresh clone can be set up following README steps alone
- [ ] Every documented command is one that exists in the repo
- [ ] Threshold value in README matches `config.py` and the calibration doc
- [ ] Disclaimer in README matches `copy.py` exactly
- [ ] Known limits reflect the build as it is, not the PRD's initial assumptions

### Out of scope

Any code change.

---

## Phase 14 — Demo runbook and final review  ·  GATE

**Goal:** make the demo unbreakable and verify submission readiness.

**Milestone:** M6. **Depends on:** P13.

### Files to create

```
docs/demo_runbook.md
```

### Runbook contents

- Pre-demo checklist: fresh `.env` verified, `python -m ingest` run, store present, app starts,
  browser zoom, terminal window with `python -m chat` open as fallback.
- The exact five questions to ask, in order, with the expected `kind` for each — the same set used in
  `sample_qa.md`.
- The two refusal questions and the PII question to demo, with expected outcomes.
- Known failure modes and what to do: Groq rate limit, store missing, wrong chunk retrieved.
- A recorded-screen backup of the three states, per PRD R10.

### Final review checklist (human)

- [ ] `README.md` setup steps work from a clean clone on a second machine
- [ ] All eight deliverables D1–D8 present and locatable
- [ ] `data/sources.csv` URLs all publicly reachable without login
- [ ] `data/chunks_dump.txt` readable and chunks independently answerable
- [ ] `data/sample_qa.md` hand-reviewed, 5–10 rows, all citations valid
- [ ] `python -m pytest -q` fully green
- [ ] No secret committed; `.env` git-ignored
- [ ] No PII in any committed file, log, or dump
- [ ] No advice, recommendation, or return comparison in any sample answer
- [ ] Every grounded sample answer has exactly one valid link and ≤ 3 sentences
- [ ] "Facts-only. No investment advice." visible in the UI
- [ ] ≤ 3-minute demo video recorded, or hosted link live
- [ ] PRD open questions 2, 4, and 5 resolved and recorded in the README

### Agent prompt

```
Implement Phase 14 of implementation.md.

Create docs/demo_runbook.md: a pre-demo checklist, the exact ordered list of questions to ask with
their expected Answer.kind, the refusal and PII questions to demo, failure modes with recovery
steps, and a note on keeping a recorded backup.

Read data/sample_qa.md for the questions rather than inventing new ones, and read
docs/threshold_calibration.md so the runbook's stated behaviour matches reality.

Then run the final review checklist in implementation.md Phase 14 yourself, checking each item
against the actual repo, and report a pass/fail table. For any FAIL, say exactly what is missing and
which phase should fix it. Do not fix anything in this phase.
```

### Exit criteria

- [ ] `docs/demo_runbook.md` complete and consistent with `sample_qa.md`
- [ ] Final review checklist run and reported, with every FAIL either fixed or explicitly deferred
- [ ] All eight PRD deliverables present

---

## Appendix A — Phase dependency graph

```
P0 config/models
 └─> P1 fetch ──> P2 extract ──> P3 chunk+dump [GATE]
                                       └─> P4 embed+store
                                              └─> P5 retrieval
P0 ──> P6 guardrails [GATE] ─┐
P5 + P6 ────────────────────> P7 generation ──> P8 pipeline ──> P9 CLI
                                                        │            └─> P10 UI
                                                        └─> P11 eval [GATE]
                                                              └─> P12 tests
                                                                    └─> P13 docs
                                                                          └─> P14 demo [GATE]
```

## Appendix B — Command reference

| Task | Command |
|------|---------|
| Install | `pip install -r requirements.txt` |
| Ingest | `python -m ingest --all --dump` |
| Force rebuild | `python -m ingest --all --force` |
| Re-fetch sources | `python -m ingest --fetch-only` |
| CLI chat | `python -m chat` |
| UI | `python -m streamlit run app.py` |
| Tests | `python -m pytest -q` |
| Fast tests | `python -m pytest -m "not slow" -q` |
| Eval baseline | `python -m src.ragmf.eval.harness --run` |
| Threshold sweep | `python -m src.ragmf.eval.harness --sweep` |
| Store inspection | `python -c "from src.ragmf.config import load; from src.ragmf.ingest.store import get_collection; print(get_collection(load(require_api_key=False)).count())"` |

## Appendix C — Definition of done

The project is done when, from a clean clone with only `requirements.txt` and `.env`:

1. `python -m ingest --all --dump` builds the store and writes a readable chunk dump, with no API
   key and no network.
2. `python -m pytest -q` is green, including the 14 PRD acceptance criteria.
3. `python -m streamlit run app.py` shows the welcome line, disclaimer, and 3 examples; every
   grounded answer has exactly one valid link, a "Last updated from sources" date, and a working
   sources expander.
4. Advice, performance, out-of-scope, and PII questions are all refused, none of them leak a value
   or a figure, and none of them require a network call.
5. Deliverables D1–D8 exist and are locatable from the README.