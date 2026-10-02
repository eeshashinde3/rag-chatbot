# Phase progress

- [x] P0  Scaffolding, config, dataclasses, deps
- [x] P1  Source acquisition -> data/raw/, sources.csv
- [x] P2  Extraction -> block stream
- [x] P3  Chunking + chunk dump  [GATE]  (3A proposal in docs/chunking_strategy.md, approved values applied: 90/20)
- [x] P4  Embedding + ChromaDB store  (170 vectors, cosine, 384-dim, verified persistent across processes)
- [x] P5  Retrieval (filters, search, gate, expand)  (49 tests; category soft preference + glossary demotion now applied in ranking; threshold 0.35 -> 0.30 from an 18-question sweep: in-scope 0.331-0.879 vs out-of-scope 0.057-0.333, ranges overlap by 0.0023)
- [x] P6  Guardrails (PII, intent, copy)  [GATE]  (128 tests pass; 0 false positives on factual and near-miss lists; PERSONAL_FINANCE covers the "my bank balance" overlap case, ordered after advice)
- [x] P7  Generation (prompts, Groq client, validators)  (31 validator tests; 8 checks in order; numeric grounding is pure/offline; prompt now forbids substituting a definition for a requested value)
- [x] P8  Pipeline orchestrator  (18 tests; 11 steps in architecture.md 5 order; logs query_hash only)
- [x] P9  CLI chat  (chat.py; `python chat.py`, set RAGMF_DEBUG_RETRIEVAL=1 to show chunks, `/reset` clears memory)
- [x] P9b Conversation memory  (src/ragmf/memory.py; last 10 messages, in-memory only; deterministic pronoun resolution runs after the guardrails and before retrieval; optional LLM rewrite off by default)
- [x] P10 Streamlit UI  (app.py; all copy from guardrails.copy; sources expander on grounded answers only; clear-chat button; disclaimer pinned above the input; no key, no env, no disk writes in app.py; 22 tests; verified `streamlit run app.py` serves, health 200)
- [ ] P11 Eval harness + threshold calibration  [GATE]  (interim 18-question sweep applied; full eval set still pending)
- [ ] P12 Tests (unit + acceptance)  (291 pass, 1 xfail: capital gains AC-7 gap, documented in tests/test_pipeline.py)
- [ ] P13 Documentation deliverables
- [ ] P14 Demo runbook + final review  [GATE]
