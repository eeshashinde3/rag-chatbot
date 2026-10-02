"""Terminal chat over pipeline.ask() for fast iteration and as the demo fallback.

Type a question, or 1-3 for an example, /exit to quit. With RAGMF_DEBUG_RETRIEVAL=1
every answer shows the chunks that were retrieved, their scores, and whether each
one was a citation candidate or a BACKGROUND neighbour.

The question is echoed to the terminal, which is fine, and never written to a log
file. The pipeline logs query hashes only.
"""

from __future__ import annotations

import os
import sys

from src.ragmf.config import ConfigError, load
from src.ragmf.guardrails import copy
from src.ragmf.guardrails.pii import redact
from src.ragmf.memory import ConversationMemory
from src.ragmf.pipeline import run

RULE = "=" * 78
THIN = "-" * 78
EXIT_COMMANDS = {"/exit", "/quit", "exit", "quit"}
RESET_COMMANDS = {"/reset", "/clear"}


def show_debug() -> bool:
    raw = (os.environ.get("RAGMF_DEBUG_RETRIEVAL") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def print_chunks(chunks: list, only_ranked: bool = False) -> None:
    """Print the retrieved chunks so an answer can be checked against its context."""
    if not chunks:
        return
    print(THIN)
    print("Retrieved chunks:")
    for scored in chunks:
        if only_ranked and scored.is_expansion:
            continue
        role = "BACKGROUND" if scored.is_expansion else f"rank {scored.rank}"
        chunk = scored.chunk
        print(f"  {scored.score:.4f}  {role:<11} {chunk.chunk_id}")
        print(f"            scheme   : {chunk.scheme}")
        print(f"            category : {chunk.category}")
        print(f"            section  : {chunk.section_title}")
        preview = chunk.text.replace("\n", " ")
        if len(preview) > 300:
            preview = preview[:300] + "..."
        print(f"            text     : {preview}")
    print(THIN)


def render(answer, debug: bool, chunks: list) -> None:
    print()
    print(answer.text)
    if answer.citation_url:
        print(f"Source: {answer.citation_url}")
    if answer.sources_date:
        print(f"Last updated from sources: {answer.sources_date}")
    if debug:
        print(f"kind: {answer.kind}")
        print_chunks(chunks)
    print()


def main() -> int:
    try:
        settings = load(require_api_key=True)
    except ConfigError as exc:
        print(f"Setup problem: {exc}")
        return 1

    print(RULE)
    print(copy.WELCOME)
    print(copy.DISCLAIMER)
    print()
    for index, example in enumerate(copy.EXAMPLE_QUESTIONS, start=1):
        print(f"  {index}. {example}")
    print(THIN)
    print("Type a question, 1-3 for an example, /reset to forget the conversation, /exit to quit.")
    if settings.memory_enabled:
        print(
            f"Follow-ups work: after naming a fund, ask 'what about its fees?' "
            f"(last {settings.memory_max_messages} messages are remembered)."
        )
    if show_debug():
        print("Debug mode: retrieved chunks will be shown for every answer.")
    print(RULE)

    debug = show_debug()
    memory = ConversationMemory(settings.memory_max_messages) if settings.memory_enabled else None

    while True:
        try:
            typed = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not typed:
            continue
        if typed.lower() in EXIT_COMMANDS:
            print("Bye.")
            return 0
        if typed.lower() in RESET_COMMANDS:
            if memory is not None:
                memory.clear()
            print("Conversation cleared. Follow-ups will no longer use earlier turns.")
            continue

        if typed in {"1", "2", "3"}:
            question = copy.EXAMPLE_QUESTIONS[int(typed) - 1]
            print(f"[{typed}] {question}")
        else:
            question = typed

        # Never echo a personal identifier back into the terminal history.
        safe_display = redact(question)
        if safe_display != question:
            print(f"[personal identifier removed from display] {safe_display}")

        try:
            answer, chunks = run(question, settings, memory)
        except Exception as exc:  # noqa: BLE001 - the CLI must not die on one bad turn
            print(f"\nSomething went wrong: {type(exc).__name__}. Please try again.\n")
            continue

        render(answer, debug, chunks)
        if memory is not None and memory.focus_scheme():
            print(f"Remembering: {memory.focus_scheme()}  (use /reset to forget)")


if __name__ == "__main__":
    sys.exit(main())
