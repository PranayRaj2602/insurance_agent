import sys
import asyncio
import concurrent.futures
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_async(coro):
    """Run an async coroutine safely from Streamlit's sync context."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


import re

def safe_md(text: str) -> str:
    """Escape currency $ signs so Streamlit doesn't treat them as LaTeX delimiters.
    Matches $ followed by digits or a space then digits (e.g. $2,500,000 or $ 35,543).
    Leaves any genuine $$...$$  LaTeX blocks untouched.
    """
    # Escape $ when immediately followed by a digit or comma-digit sequence
    return re.sub(r'\$(?=[\d,])', r'\\$', text)

import streamlit as st
from src.config import CLAIMS_JSON, DATA_DIR, ANTHROPIC_API_KEY
from src.tools.document_store import DocumentStore
from src.agents.ingestion import IngestionAgent
from src.agents.summarization import SummarizationAgent
from src.agents.chat import ChatAgent

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Insurance Intelligence",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: 600; }
.claim-card { background: #f0f4f8; border-radius: 8px; padding: 10px; margin: 4px 0; }
.agent-badge { background: #e8f4f8; border-left: 3px solid #2196F3;
               padding: 6px 10px; margin: 4px 0; border-radius: 0 4px 4px 0; font-size: 0.85rem; }
.risk-high { color: #d32f2f; font-weight: bold; }
.risk-medium { color: #f57c00; font-weight: bold; }
.risk-low { color: #388e3c; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "store_initialized": False,
        "selected_claim": None,
        "summaries_cache": {},
        "messages": [],
        "store": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ── Store initialization ──────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_store() -> DocumentStore:
    return DocumentStore()


store: DocumentStore = get_store()
st.session_state.store = store

if not st.session_state.store_initialized:
    if not store.is_initialized():
        with st.spinner("📚 Loading 100 claim documents into vector store... (first run only)"):
            count = store.initialize_from_json(CLAIMS_JSON)
        st.success(f"✅ Loaded {count} document chunks.")
    st.session_state.store_initialized = True

ingestion_agent = IngestionAgent(store)
summarization_agent = SummarizationAgent(store)
chat_agent = ChatAgent(store, st.session_state.summaries_cache)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏥 Insurance Intelligence")
    st.caption("P&C Claims Analysis System")
    st.divider()

    if not ANTHROPIC_API_KEY:
        st.error("⚠️ ANTHROPIC_API_KEY not set. Add it to .env")

    # Claim selector
    st.subheader("📁 Claims")
    claims = store.list_claims()
    if claims:
        selected = st.selectbox(
            "Select a claim",
            options=claims,
            index=claims.index(st.session_state.selected_claim)
            if st.session_state.selected_claim in claims else 0,
            key="claim_selector",
        )
        st.session_state.selected_claim = selected

        # Show doc types for selected claim
        docs = store.get_by_claim(selected)
        if docs:
            doc_types = [d["metadata"]["file_type"] for d in docs]
            st.caption(f"**{len(doc_types)} documents:**")
            for dt in doc_types:
                st.caption(f"  • {dt}")
    else:
        st.info("No claims loaded yet.")

    st.divider()

    # Upload new document
    st.subheader("📤 Upload Document")
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"], key="pdf_uploader")
    if uploaded and st.button("🔄 Ingest Document", use_container_width=True):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        try:
            with st.spinner("Extracting and classifying..."):
                meta = ingestion_agent.ingest(tmp_path)
            st.success(f"✅ Ingested: **{meta['claim_id']}** / {meta['file_type']}")
            if meta.get("insured_name"):
                st.caption(f"Insured: {meta['insured_name']}")
            if meta.get("date_of_loss"):
                st.caption(f"Date of loss: {meta['date_of_loss']}")
            # Refresh claim list
            st.rerun()
        except Exception as e:
            st.error(f"Ingestion failed: {e}")
        finally:
            os.unlink(tmp_path)

    st.divider()
    st.caption(f"Vector store: **{store._col.count()} chunks**")


# ── Main area ─────────────────────────────────────────────────────────────────
claim_id = st.session_state.selected_claim

if claim_id:
    st.header(f"Claim: `{claim_id}`")
else:
    st.header("Insurance Intelligence System")
    st.info("Select a claim from the sidebar to get started.")

tab_summary, tab_chat = st.tabs(["📊 Summary", "💬 Chat"])


# ── Summary Tab ───────────────────────────────────────────────────────────────
with tab_summary:
    if not claim_id:
        st.info("Select a claim from the sidebar.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"Claim Intelligence Report")
        with col2:
            summarize_btn = st.button(
                "▶ Summarize Claim",
                use_container_width=True,
                type="primary",
                key="summarize_btn",
            )

        if summarize_btn:
            with st.status("Running multi-agent analysis...", expanded=True) as status:
                st.write("🔍 **Facts Agent** (Haiku) — extracting claim facts...")
                st.write("📋 **Coverage Agent** (Haiku) — analyzing policy coverage...")
                st.write("⚠️ **Risk Agent** (Haiku) — assessing risk flags...")
                st.write("📅 **Timeline Agent** (Haiku) — building event sequence...")
                st.write("✍️ **Synthesis Agent** (Sonnet) — generating report...")

                try:
                    result = run_async(summarization_agent.summarize(claim_id))
                    st.session_state.summaries_cache[claim_id] = result
                    status.update(label="✅ Analysis complete!", state="complete")
                except Exception as e:
                    status.update(label=f"❌ Error: {e}", state="error")
                    st.error(str(e))
                    result = None
        else:
            result = st.session_state.summaries_cache.get(claim_id)

        if result and "error" not in result:
            # Main summary
            st.markdown(safe_md(result["summary"]))

            # Agent outputs in expanders
            st.divider()
            col_f, col_c = st.columns(2)

            with col_f:
                with st.expander("🔍 Facts Agent Output"):
                    facts = result.get("facts", {})
                    for k, v in facts.items():
                        if v and k != "document_types":
                            st.markdown(safe_md(f"**{k.replace('_', ' ').title()}:** {v}"))
                    if facts.get("document_types"):
                        st.markdown(f"**Documents:** {', '.join(facts['document_types'])}")

            with col_c:
                with st.expander("📋 Coverage Agent Output"):
                    cov = result.get("coverage", {})
                    for k, v in cov.items():
                        if v and k != "gaps_identified":
                            st.markdown(safe_md(f"**{k.replace('_', ' ').title()}:** {v}"))
                    gaps = cov.get("gaps_identified", [])
                    if gaps:
                        st.markdown("**Gaps:**")
                        for g in gaps:
                            st.markdown(safe_md(f"- {g}"))

            col_r, col_t = st.columns(2)

            with col_r:
                with st.expander("⚠️ Risk Agent Output"):
                    risk = result.get("risk", {})
                    risk_level = risk.get("overall_risk", "Unknown")
                    color = {"High": "risk-high", "Medium": "risk-medium", "Low": "risk-low"}.get(risk_level, "")
                    st.markdown(f'**Risk Level:** <span class="{color}">{risk_level}</span>', unsafe_allow_html=True)
                    for section, items in [
                        ("Red Flags", risk.get("red_flags", [])),
                        ("Anomalies", risk.get("anomalies", [])),
                        ("Fraud Indicators", risk.get("fraud_indicators", [])),
                    ]:
                        if items:
                            st.markdown(f"**{section}:**")
                            for item in items:
                                st.markdown(f"- {item}")

            with col_t:
                with st.expander("📅 Timeline Agent Output"):
                    timeline = result.get("timeline", {})
                    events = timeline.get("events", [])
                    if events:
                        for event in events:
                            date = event.get("date", "?")
                            source = event.get("source", "")
                            st.markdown(
                                f"**{date}** — {event['event']}"
                                + (f" *(from {source})*" if source else "")
                            )
                    status_str = timeline.get("claim_status")
                    if status_str:
                        st.markdown(f"\n**Current Status:** {status_str}")

        elif result and "error" in result:
            st.error(result["error"])
        elif not summarize_btn:
            st.info("Click **▶ Summarize Claim** to run the multi-agent analysis.")


# ── Chat Tab ──────────────────────────────────────────────────────────────────
with tab_chat:
    st.subheader("Chat with your claim documents")

    if claim_id:
        st.caption(f"Context: **{claim_id}** — ask about this claim or any claim in the corpus.")
    else:
        st.caption("No claim selected — you can still ask general questions across all claims.")

    # Display chat history
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        # content may be a list (for tool_use assistant turns) — extract text
        if isinstance(content, list):
            text = " ".join(
                b.text if hasattr(b, "text") else b.get("text", "")
                for b in content
                if (hasattr(b, "type") and b.type == "text")
                or (isinstance(b, dict) and b.get("type") == "text")
            )
        else:
            text = str(content)

        if role == "user" and not isinstance(content, list):
            # Strip context injection prefix for display
            display_text = text.split("\n\n", 1)[-1] if text.startswith("[Context:") else text
            with st.chat_message("user"):
                st.markdown(display_text)
        elif role == "assistant" and text:
            with st.chat_message("assistant"):
                st.markdown(safe_md(text))

    # Chat input
    user_input = st.chat_input("Ask about claims, coverage, or any document...")
    if user_input:
        # Show user message
        with st.chat_message("user"):
            st.markdown(user_input)

        # Build history for agent (exclude the current user message — added inside agent)
        history = []
        for msg in st.session_state.messages:
            role = msg["role"]
            content = msg["content"]
            if isinstance(content, list):
                # For assistant turns with tool_use, keep full content
                history.append({"role": role, "content": content})
            else:
                text = str(content)
                # Skip empty
                if text.strip():
                    history.append({"role": role, "content": text})

        # Stream response
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            try:
                for chunk in chat_agent.stream_response(user_input, history, claim_id):
                    full_response += chunk
                    response_placeholder.markdown(safe_md(full_response) + "▌")
                response_placeholder.markdown(safe_md(full_response))
            except Exception as e:
                st.error(f"Error: {e}")
                full_response = f"Error: {e}"

        # Persist to history
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # Clear chat button
    if st.session_state.messages:
        if st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()
