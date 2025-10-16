from __future__ import annotations
"""Streamlit Chat UI for the CX Agent SDK.

This lightweight interface exercises multi-turn conversation memory and the
LLM-based intent routing path. It wires the same components as the demo script
and preserves session history via the `InMemoryConversationMemory` adapter.

Run:
  streamlit run src/ui/chat.py

Environment:
  - OPENAI_API_KEY must be set for the `OpenAIProvider`.
  - Optional: OPENAI_MODEL (defaults to `gpt-4o-mini`).
"""

import uuid
import os
import time
import sys
import pathlib
import streamlit as st

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# Ensure project root is on sys.path when running via `streamlit run src/ui/chat.py`
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.types import Interaction
from src.agent.router import AgentRouter
from src.adapters.datasource.json_data_source import JSONDataSource
from src.adapters.policy.null_policy import NullPolicyEngine
from src.adapters.telemetry.print_sink import PrintSink
from src.adapters.executor.local_executor import LocalExecutor
from src.adapters.intents.yaml_registry import YAMLIntentsRegistry
from src.adapters.llm.openai_provider import OpenAIProvider
from src.adapters.classifier.llm_intent_classifier import LLMIntentClassifier
from src.adapters.planner.simple_planner import SimplePlanner
from src.adapters.memory.in_memory import InMemoryConversationMemory
from src.tools.check_order_status import make_check_order_status


@st.cache_resource(show_spinner=False)
def get_router_and_memory():
    """Construct and cache the AgentRouter and its memory instance.

    The memory object is returned so the UI can render message history directly
    from the authoritative store used by the router.
    """
    # Data and tools
    ds = JSONDataSource("data/orders.json")
    executor = LocalExecutor()
    executor.register("check_order_status", make_check_order_status(ds))

    # Policies and telemetry
    policy = NullPolicyEngine()
    telemetry = PrintSink()

    # Intents + classifier (LLM-based via OpenAI)
    intents = YAMLIntentsRegistry("config/intents.yaml")
    llm = OpenAIProvider(model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini")
    classifier = LLMIntentClassifier(llm)
    planner = SimplePlanner()
    memory = InMemoryConversationMemory(max_messages=20)

    router = AgentRouter(
        intents=intents,
        classifier=classifier,
        planner=planner,
        policy=policy,
        executor=executor,
        telemetry=telemetry,
        memory=memory,
    )
    return router, memory


def ensure_session_id() -> str:
    """Create or return a stable session id for this Streamlit session."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"ui-{uuid.uuid4().hex[:8]}"
    return st.session_state.session_id


def render_sidebar(sid: str, ready: bool) -> None:
    """Sidebar with controls and quick info."""
    st.sidebar.header("CX Agent Chat")
    st.sidebar.caption("Multi-turn memory demo")
    st.sidebar.write(f"Session: `{sid}`")
    if not ready:
        st.sidebar.error("OPENAI_API_KEY not set. Set it and rerun.")
    if st.sidebar.button("Reset Conversation", use_container_width=True):
        # Clear memory for this session and the chat transcript
        try:
            _, memory = get_router_and_memory()
            memory.for_session(sid).clear()
        except Exception:
            pass
        st.session_state.pop("transcript", None)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="CX Agent Chat", page_icon="🤖", layout="centered")
    st.title("CX Agent Chat")
    st.caption("Test multi-turn memory, parameter collection, and tool execution.")

    sid = ensure_session_id()
    ready = bool(os.getenv("OPENAI_API_KEY"))
    render_sidebar(sid, ready)

    # Build router lazily and surface provider errors nicely
    router = None
    memory = None
    error_text = None
    if ready:
        try:
            router, memory = get_router_and_memory()
        except Exception as exc:  # e.g., openai package missing
            error_text = str(exc)
    else:
        error_text = "OPENAI_API_KEY is required."

    if error_text:
        st.error(f"Cannot initialize agent: {error_text}")
        with st.expander("Environment diagnostics", expanded=False):
            import platform
            st.write({
                "python": platform.python_version(),
                "streamlit": getattr(st, "__version__", "unknown"),
                "OPENAI_API_KEY_present": bool(os.getenv("OPENAI_API_KEY")),
                "repo_root": str(ROOT),
            })

    # Render existing memory-backed transcript
    sesh = memory.for_session(sid)
    for msg in sesh.history():
        role = msg.get("role", "user")
        if role not in ("user", "agent"):
            continue
        with st.chat_message(role):
            st.write(msg.get("text", ""))

    # Primary chat input (sticky footer)
    prompt = st.chat_input("Type a message…")
    if prompt:
        # Echo user message in UI immediately
        with st.chat_message("user"):
            st.write(prompt)

        if router is None:
            with st.chat_message("agent"):
                st.warning("Agent is not initialized. Check the error above (likely OpenAI SDK or API key). Run `pip install -r requirements.txt` and set `OPENAI_API_KEY`.")
        else:
            # Build interaction and call router
            interaction: Interaction = {
                "id": f"msg-{int(time.time()*1000)}",
                "text": prompt,
                "context": {"session_id": sid, "channel": "chat"},
            }
            response = router.handle(interaction)

            # Display agent response
            with st.chat_message("agent"):
                st.write(response.get("text", ""))


if __name__ == "__main__":
    main()
