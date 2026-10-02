"""Streamlit chat UI (implementation.md Phase 10, PRD FR-6).

Every user-facing string is imported from guardrails.copy. Nothing is hardcoded
here, including the welcome line, the disclaimer, and the examples, so the CLI and
the browser can never disagree about what the product says.

The API key is never read or referenced in this file. ask() owns configuration, and
this module calls no configuration loader and touches no environment variable
directly; the only settings it needs come back from the same pipeline entry point
the CLI uses. Nothing is written to disk: the
message list and the conversation memory live in st.session_state for this browser
session only.

Render order follows implementation.md: welcome, history, then the disclaimer
pinned directly above the input so it stays visible in every state.
"""

from __future__ import annotations

import streamlit as st

from src.ragmf.config import ConfigError
from src.ragmf.guardrails import copy
from src.ragmf.guardrails.pii import redact
from src.ragmf.memory import ConversationMemory
from src.ragmf.models import Answer
from src.ragmf.pipeline import ask

SECTION_FALLBACK = "Overview"
SOURCES_EXPANDER = "Show sources"
SOURCE_LINE = "Source: {label}"
LAST_UPDATED_LINE = "Last updated from sources: {date}"
EXAMPLE_PREFIX = "Try: "
CLEAR_CHAT_LABEL = "Clear chat"
CLEAR_CHAT_HELP = "Forget this conversation and start over."


def _seed_session() -> None:
    """Create the per-session containers once per browser session."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationMemory()
    if "pending" not in st.session_state:
        # Set by the example buttons, consumed by the chat_input on the next rerun.
        st.session_state.pending = None


def _render_sources(answer: Answer) -> None:
    """List the chunks that produced a grounded answer, one per row."""
    if not answer.show_context:
        return
    with st.expander(SOURCES_EXPANDER):
        for view in answer.show_context:
            st.markdown(f"**{view.scheme}** — {view.section_title or SECTION_FALLBACK}")
            st.caption(f"score {view.score:.4f} · [page]({view.url})")


def _render_answer(answer: Answer) -> None:
    """One assistant turn. The link is rendered the same way for every kind."""
    if answer.kind == "error":
        st.warning(answer.text)
        return

    st.write(answer.text)

    if answer.citation_url:
        label = answer.citation_label or answer.citation_url
        st.markdown(f"{SOURCE_LINE.format(label=label)}: [{label}]({answer.citation_url})")
    if answer.sources_date:
        st.caption(LAST_UPDATED_LINE.format(date=answer.sources_date))

    # Only a grounded answer actually cited something, so refusals get no expander.
    if answer.kind == "grounded":
        _render_sources(answer)


def _render_history() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                _render_answer(message["answer"])
            else:
                st.write(message["content"])


def _answer_for(question: str) -> Answer:
    """Ask one question and always return an Answer, never an exception.

    ask() already turns its own failures into kind="error"; this catches the ones it
    cannot see, so a single bad turn cannot end the browser session.
    """
    try:
        return ask(question, memory=st.session_state.memory)
    except ConfigError as exc:
        return Answer(kind="error", text=str(exc), notes="preflight failed")
    except Exception:  # noqa: BLE001 - one bad turn must not kill the session
        return Answer(
            kind="error",
            text=copy.render(copy.ERROR_GENERIC, copy.educational_link()),
            notes="unexpected failure",
        )


def _handle(question: str) -> None:
    """Run one turn: ask(), record it, and let the rerun redraw the history."""
    st.session_state.messages.append(
        {"role": "user", "content": redact(question), "answer": None}
    )

    with st.spinner("Looking that up..."):
        answer = _answer_for(question)

    st.session_state.messages.append({"role": "assistant", "content": "", "answer": answer})


def main() -> None:
    st.set_page_config(page_title="MF Facts Assistant", layout="centered")
    _seed_session()

    st.title("MF Facts Assistant")
    st.write(copy.WELCOME)

    for example in copy.EXAMPLE_QUESTIONS:
        if st.button(f"{EXAMPLE_PREFIX}{example}", key=f"example_{example[:32]}"):
            st.session_state.pending = example

    _render_history()

    # Toolbar first, so the disclaimer is the last element before the input and stays
    # visible in every state, including while a spinner is up and after a refusal.
    if st.button(CLEAR_CHAT_LABEL, help=CLEAR_CHAT_HELP):
        st.session_state.messages = []
        st.session_state.memory = ConversationMemory()
        st.session_state.pending = None
        st.rerun()

    st.caption(copy.DISCLAIMER)

    typed = st.chat_input("Ask a factual question about the HDFC schemes")
    question = st.session_state.pending or typed
    if question:
        st.session_state.pending = None
        _handle(question)
        st.rerun()


if __name__ == "__main__":
    main()
