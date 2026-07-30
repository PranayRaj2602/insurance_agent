import sys
import asyncio
import concurrent.futures
import re
import json
import shutil
from pathlib import Path
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st  # must be before any @st.dialog usage


def run_async(coro):
    """Run an async coroutine safely from Streamlit's sync context."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()

def safe_md(text: str) -> str:
    """Escape currency $ signs so Streamlit doesn't treat them as LaTeX delimiters."""
    return re.sub(r'\$(?=[\d,])', r'\\$', text)


def find_pdf(claim_id: str, path: str):
    """Locate a PDF file for a citation. `path` is the filename stored in metadata."""
    filename = Path(path).name
    pdf_path = DATA_DIR / claim_id / filename
    if pdf_path.exists():
        return pdf_path
    # Fallback: search the claim folder for a matching file_type
    claim_dir = DATA_DIR / claim_id
    if claim_dir.exists():
        pdfs = list(claim_dir.glob("*.pdf"))
        if pdfs:
            return pdfs[0]
    return None


@st.dialog("📄 Document Viewer", width="large")
def open_pdf_modal(claim_id: str, file_type: str, path: str):
    """Full-screen PDF viewer — all pages stacked, user scrolls. No reruns."""
    import pypdfium2 as pdfium

    # ── CSS: stretch dialog to near-fullscreen, allow scrolling ──────────────
    st.markdown("""
    <style>
    div[data-baseweb="modal"] > div {
        max-width: 94vw !important;
        width: 94vw !important;
        max-height: 94vh !important;
        height: 94vh !important;
        border-radius: 10px !important;
    }
    div[data-baseweb="modal"] > div > div {
        max-height: 92vh !important;
        overflow-y: auto !important;
        padding: 16px 20px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    pdf_path = find_pdf(claim_id, path)
    if not pdf_path:
        st.warning("PDF file not found locally.")
        return

    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        n_pages = len(pdf)

        # ── Header row: title + download ─────────────────────────────────────
        col_t, col_dl = st.columns([4, 1])
        with col_t:
            st.markdown(
                f"**{claim_id} — {file_type}** &nbsp; "
                f'<span style="color:#888;font-size:0.85rem">'
                f"{pdf_path.name} · {n_pages} page{'s' if n_pages > 1 else ''}"
                f"</span>",
                unsafe_allow_html=True,
            )
        with col_dl:
            with open(pdf_path, "rb") as f:
                st.download_button(
                    "⬇ Download", data=f, file_name=pdf_path.name,
                    mime="application/pdf", key=f"dl_{claim_id}_{file_type}",
                    use_container_width=True,
                )
        st.divider()

        # ── Render ALL pages as base64 → single HTML block (forces 100% width) ─
        import io, base64 as b64
        pages_html = []
        for i in range(n_pages):
            buf = io.BytesIO()
            pdf[i].render(scale=2.8).to_pil().save(buf, format="PNG")
            img_b64 = b64.b64encode(buf.getvalue()).decode()
            label = f'<div style="text-align:center;color:#999;font-size:0.78rem;margin:4px 0 8px">Page {i+1} of {n_pages}</div>' if n_pages > 1 else ""
            separator = '<div style="height:1px;background:#e8e8e8;margin:10px 0"></div>' if i < n_pages - 1 else ""
            pages_html.append(
                f'<img src="data:image/png;base64,{img_b64}" '
                f'style="width:100%;display:block;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,0.1)"/>'
                f'{label}{separator}'
            )
        pdf.close()

        st.markdown(
            f'<div style="width:100%">{"".join(pages_html)}</div>',
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.error(f"Could not render PDF: {e}")


def render_citations(citations: list, key_prefix: str):
    """Render simple inline reference tags below a chat/summary response."""
    if not citations:
        return
    seen, unique = set(), []
    for c in citations:
        k = (c["claim_id"], c["file_type"])
        if k not in seen:
            seen.add(k)
            unique.append(c)
    refs = " &nbsp;·&nbsp; ".join(
        f'<span style="background:#e8f4f8;border:1px solid #b3d4f0;border-radius:4px;'
        f'padding:2px 8px;font-size:0.8rem;color:#1565c0">'
        f'📄 {c["claim_id"]} — {c["file_type"]}</span>'
        for c in unique
    )
    st.markdown(f'<div style="margin-top:6px">**Ref:** {refs}</div>',
                unsafe_allow_html=True)

from src.config import CLAIMS_JSON, DATA_DIR, ANTHROPIC_API_KEY, CLAIMS_METADATA_JSON
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

# ── Dark Theme CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Palette ─────────────────────────────────────────────────────────────────
   bg-deep:   #0d0f1a   main canvas
   bg-card:   #161827   card / sidebar surface
   bg-hover:  #1e2235   hover / active
   teal:      #2dd4bf   primary accent
   orange:    #f5a623   warning / highlight
   text-hi:   #f0f2ff   headings
   text-mid:  #9ca3b8   secondary text
   border:    #252840   subtle borders
──────────────────────────────────────────────────────────────────────────── */

/* ── Global background ──────────────────────────────────────────────────── */
[data-testid="stApp"],
[data-testid="stMain"],
.main .block-container          { background: #0d0f1a !important; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div { background: #161827 !important; border-right: 1px solid #252840 !important; }

[data-testid="stSidebar"] * { color: #9ca3b8 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] strong { color: #f0f2ff !important; }
[data-testid="stSidebar"] .stCaption p { color: #6b7280 !important; font-size: 0.75rem !important; }

/* ── All body text ───────────────────────────────────────────────────────── */
p, span, li, label, div, td, th { color: #9ca3b8; }
h1, h2, h3, h4, h5              { color: #f0f2ff !important; letter-spacing: 0.01em; }
strong, b                        { color: #d4d8f0 !important; }

/* ── App header / top bar ────────────────────────────────────────────────── */
[data-testid="stHeader"]         { background: #0d0f1a !important; border-bottom: 1px solid #252840; }

/* ── Main headings ───────────────────────────────────────────────────────── */
[data-testid="stHeading"] h1,
[data-testid="stHeading"] h2,
[data-testid="stHeading"] h3    { color: #f0f2ff !important; font-weight: 700; letter-spacing: 0.02em; }

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"]           { border-bottom: 1px solid #252840; }
[data-baseweb="tab"]             { font-size: 0.9rem !important; font-weight: 600 !important;
                                   color: #9ca3b8 !important; letter-spacing: 0.06em;
                                   text-transform: uppercase; padding: 10px 18px !important; }
[data-baseweb="tab"][aria-selected="true"]
                                 { color: #2dd4bf !important; border-bottom: 2px solid #2dd4bf !important; }
[data-baseweb="tab-border"]      { background: #2dd4bf !important; }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-primary"] button,
button[kind="primary"]           { background: #2dd4bf !important; color: #0d0f1a !important;
                                   border: none !important; font-weight: 700 !important;
                                   letter-spacing: 0.03em; border-radius: 6px !important; }
[data-testid="stBaseButton-secondary"] button,
button[kind="secondary"]         { background: #1e2235 !important; color: #d4d8f0 !important;
                                   border: 1px solid #2dd4bf !important; border-radius: 6px !important;
                                   font-weight: 600 !important; }
button                           { background: #1e2235 !important; color: #d4d8f0 !important;
                                   border: 1px solid #252840 !important; border-radius: 6px !important; }
button:hover                     { border-color: #2dd4bf !important; color: #2dd4bf !important; }

/* ── Inputs, selectbox, date picker ─────────────────────────────────────── */
input, textarea                  { background: #1e2235 !important; color: #f0f2ff !important;
                                   border: 1px solid #252840 !important; border-radius: 6px !important; }
input:focus, textarea:focus      { border-color: #2dd4bf !important; box-shadow: 0 0 0 2px rgba(45,212,191,0.2) !important; }
[data-baseweb="select"] > div,
[data-baseweb="input"] > div     { background: #1e2235 !important; border-color: #252840 !important; }
[data-baseweb="select"] *,
[data-baseweb="input"] *        { color: #f0f2ff !important; }
[data-baseweb="popover"] > div,
[data-baseweb="menu"]            { background: #1e2235 !important; border: 1px solid #252840 !important; }
[role="option"]                  { background: #1e2235 !important; color: #d4d8f0 !important; }
[role="option"]:hover            { background: #2dd4bf20 !important; color: #2dd4bf !important; }

/* ── Expanders ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"]       { background: #161827 !important; border: 1px solid #252840 !important;
                                   border-radius: 8px !important; margin-bottom: 6px; }
[data-testid="stExpander"] summary
                                 { color: #d4d8f0 !important; font-weight: 600; font-size: 0.88rem;
                                   letter-spacing: 0.04em; }
[data-testid="stExpander"] summary:hover
                                 { color: #2dd4bf !important; }

/* ── Status / alert boxes ────────────────────────────────────────────────── */
[data-testid="stAlert"]          { border-radius: 8px !important; border-left-width: 3px !important; }
[data-testid="stAlert"][data-baseweb="notification"][kind="info"]
                                 { background: #0d1f2d !important; border-color: #2dd4bf !important; }
[data-testid="stAlert"][data-baseweb="notification"][kind="success"]
                                 { background: #0d2310 !important; border-color: #22c55e !important; }
[data-testid="stAlert"][data-baseweb="notification"][kind="error"]
                                 { background: #2d0d0d !important; border-color: #ef4444 !important; }
[data-testid="stAlert"][data-baseweb="notification"][kind="warning"]
                                 { background: #2d1a0d !important; border-color: #f5a623 !important; }
[data-testid="stStatusWidget"]   { background: #161827 !important; border: 1px solid #252840 !important;
                                   border-radius: 8px !important; }

/* ── Dividers / HR ───────────────────────────────────────────────────────── */
hr, [data-testid="stDivider"]    { border-color: #252840 !important; opacity: 0.6; }

/* ── Progress bar ────────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div { background: #1e2235 !important; border-radius: 4px; }
[data-testid="stProgressBar"] > div > div
                                 { background: linear-gradient(90deg, #2dd4bf, #22d3ee) !important; }

/* ── Spinner ─────────────────────────────────────────────────────────────── */
[data-testid="stSpinner"] *      { color: #2dd4bf !important; }

/* ── Metrics ─────────────────────────────────────────────────────────────── */
[data-testid="stMetric"]         { background: #161827 !important; border: 1px solid #252840;
                                   border-radius: 8px; padding: 12px !important; }
[data-testid="stMetricLabel"]    { color: #9ca3b8 !important; font-size: 0.72rem !important;
                                   text-transform: uppercase; letter-spacing: 0.08em; }
[data-testid="stMetricValue"]    { color: #f0f2ff !important; font-weight: 700 !important; }

/* ── Captions ────────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p,
small, .stCaption               { color: #6b7280 !important; font-size: 0.78rem !important; }

/* ── Number input / slider ───────────────────────────────────────────────── */
[data-testid="stSlider"] [data-testid="stSliderTrack"]
                                 { background: #252840 !important; }
[data-testid="stSlider"] [data-testid="stSliderTrackFill"]
                                 { background: #2dd4bf !important; }

/* ── File uploader ───────────────────────────────────────────────────────── */
[data-testid="stFileUploader"]   { background: #161827 !important; border: 1px dashed #252840 !important;
                                   border-radius: 8px !important; }
[data-testid="stFileUploader"]:hover
                                 { border-color: #2dd4bf !important; }

/* ── Data tables / code blocks ───────────────────────────────────────────── */
[data-testid="stCodeBlock"] pre,
pre, code                        { background: #0a0c16 !important; color: #a5f3eb !important;
                                   border: 1px solid #252840 !important; border-radius: 6px !important; }

/* ── Dialog modal ────────────────────────────────────────────────────────── */
[data-baseweb="modal"] > div     { background: #161827 !important; border: 1px solid #252840 !important; }
[data-testid="stDialog"] *       { color: #d4d8f0; }

/* ── Chat messages ───────────────────────────────────────────────────────── */
[data-testid="stChatMessage"]    { background: #161827 !important; border: 1px solid #252840;
                                   border-radius: 8px !important; margin-bottom: 8px; }
[data-testid="stChatInput"] textarea
                                 { background: #1e2235 !important; border-color: #252840 !important;
                                   color: #f0f2ff !important; }
[data-testid="stChatInput"] textarea:focus
                                 { border-color: #2dd4bf !important; }

/* ── Ref badges (citations) ──────────────────────────────────────────────── */
.ref-badge                       { background: rgba(45,212,191,0.12) !important;
                                   border: 1px solid rgba(45,212,191,0.35) !important;
                                   color: #2dd4bf !important; }

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar              { width: 6px; height: 6px; }
::-webkit-scrollbar-track        { background: #0d0f1a; }
::-webkit-scrollbar-thumb        { background: #252840; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover  { background: #2dd4bf40; }

/* ── App title in sidebar ────────────────────────────────────────────────── */
[data-testid="stSidebar"] h1     { font-size: 1.15rem !important; font-weight: 800 !important;
                                   color: #f0f2ff !important; letter-spacing: 0.05em !important; }

/* ── Custom semantic classes ─────────────────────────────────────────────── */
.risk-high   { color: #ef4444 !important; font-weight: 700 !important; }
.risk-medium { color: #f5a623 !important; font-weight: 700 !important; }
.risk-low    { color: #2dd4bf !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)


# ── Claims metadata helpers ───────────────────────────────────────────────────
def load_claims_metadata() -> dict:
    if CLAIMS_METADATA_JSON.exists():
        with open(CLAIMS_METADATA_JSON) as f:
            return json.load(f)
    return {}

def save_claims_metadata(meta: dict) -> None:
    tmp = CLAIMS_METADATA_JSON.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    import os; os.replace(tmp, CLAIMS_METADATA_JSON)

def next_claim_id(existing_ids: list) -> str:
    nums = [int(m.group(1)) for cid in existing_ids
            if (m := re.match(r"CLM-(\d+)$", cid, re.IGNORECASE))]
    return f"CLM-{(max(nums) + 1) if nums else 1:08d}"

# File type label mapping from filename stems
_FILE_TYPE_MAP = {
    "fnol": "FNOL", "claim fnol": "FNOL", "claim_fnol": "FNOL",
    "policy": "Policy",
    "adjuster notes": "Adjuster Notes", "adjuster_notes": "Adjuster Notes",
    "claimant statement": "Claimant Statement",
    "coverage determination": "Coverage Determination",
    "proof of loss": "Proof Of Loss", "claim proof of loss": "Claim Proof Of Loss",
    "investigation report": "Investigation Report",
    "reserve analysis": "Reserve Analysis",
    "settlement agreement": "Settlement Agreement",
    "payment authorization": "Payment Authorization",
    "final settlement": "Final Settlement",
    "closure summary": "Closure Summary",
    "reopening notice": "Reopening Notice",
    "adjuster report": "Adjuster Notes",
}


# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "store_initialized": False,
        "selected_claim": None,
        "summaries_cache": {},
        "messages": [],
        "store": None,
        "citations_by_msg": {},
        "view_doc": None,
        "new_claim_ids": set(),    # claim IDs created this session → 🆕 badge
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

    # ── Claim selector ────────────────────────────────────────────────────────
    st.subheader("📁 Claims")
    claims = store.list_claims()
    new_ids = st.session_state.get("new_claim_ids", set())
    if claims:
        claims_sorted = sorted(claims, key=lambda c: (c not in new_ids, c))
        selected = st.selectbox(
            "Select a claim",
            options=claims_sorted,
            format_func=lambda c: f"🆕 {c}" if c in new_ids else c,
            index=claims_sorted.index(st.session_state.selected_claim)
            if st.session_state.selected_claim in claims_sorted else 0,
            key="claim_selector",
        )
        st.session_state.selected_claim = selected

        # Show metadata for selected claim if it was user-created
        claims_meta = load_claims_metadata()
        if selected in claims_meta:
            m = claims_meta[selected]
            if m.get("insured_name"):
                st.caption(f"**Insured:** {m['insured_name']}")
            if m.get("policy_id"):
                st.caption(f"**Policy:** {m['policy_id']}")

        # Clickable doc buttons
        docs = store.get_by_claim(selected)
        if docs:
            st.caption(f"**{len(docs)} documents** — click to view:")
            for d in docs:
                ft = d["metadata"]["file_type"]
                path = d["metadata"].get("path", "")
                if st.button(f"📄 {ft}", key=f"doc_btn_{selected}_{ft}",
                             use_container_width=True):
                    open_pdf_modal(selected, ft, path)
    else:
        st.info("No claims loaded yet.")

    # ── Create New Claim ──────────────────────────────────────────────────────
    st.divider()
    with st.expander("➕ Create New Claim", expanded=False):
        claims_meta = load_claims_metadata()
        all_known = list(set(store.list_claims()) | set(claims_meta.keys()))
        suggested = next_claim_id(all_known)

        new_cid = st.text_input("Claim ID", value=suggested, key="nc_id").strip().upper()
        nc_insured = st.text_input("Insured Name", key="nc_insured")
        nc_policy  = st.text_input("Policy Number", key="nc_policy")
        nc_dol     = st.date_input("Date of Loss", key="nc_dol")
        nc_cause   = st.selectbox("Cause of Loss",
                       ["Fire", "Flood", "Theft", "Liability",
                        "Wind/Hail", "Water Damage", "Other"], key="nc_cause")
        nc_files   = st.file_uploader("Upload PDFs (one or more)",
                       type=["pdf"], accept_multiple_files=True, key="nc_pdfs")

        if st.button("✅ Create Claim", type="primary",
                     use_container_width=True, key="nc_submit"):
            errors = []
            if not new_cid:
                errors.append("Claim ID is required.")
            elif new_cid in all_known:
                errors.append(f"{new_cid} already exists.")
            if not nc_files:
                errors.append("Upload at least one PDF.")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                claim_dir = DATA_DIR / new_cid
                claim_dir.mkdir(parents=True, exist_ok=True)
                bar = st.progress(0)
                n   = len(nc_files)
                ok  = 0
                for i, uf in enumerate(nc_files):
                    # Derive file type from filename
                    stem = re.sub(r"[_-]clm[-_]?\d+$", "", Path(uf.name).stem, flags=re.IGNORECASE)
                    hint = stem.replace("_", " ").replace("-", " ").title()
                    hint = _FILE_TYPE_MAP.get(hint.lower(), hint)
                    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
                    dest = claim_dir / f"{slug}_{new_cid}.pdf"
                    dest.write_bytes(uf.read())
                    try:
                        ingestion_agent.ingest_with_meta(
                            str(dest), new_cid, hint,
                            {"insured_name": nc_insured, "policy_id": nc_policy,
                             "date_of_loss": str(nc_dol), "cause_of_loss": nc_cause},
                        )
                        ok += 1
                    except Exception as ex:
                        st.warning(f"Could not ingest {uf.name}: {ex}")
                    bar.progress((i + 1) / n)

                claims_meta[new_cid] = {
                    "insured_name": nc_insured, "policy_id": nc_policy,
                    "date_of_loss": str(nc_dol), "cause_of_loss": nc_cause,
                    "created_at": datetime.now().isoformat(), "file_count": ok,
                }
                save_claims_metadata(claims_meta)
                st.session_state.new_claim_ids.add(new_cid)
                st.session_state.selected_claim = new_cid
                st.success(f"✅ {new_cid} created — {ok}/{n} documents ingested.")
                st.rerun()

    # ── Upload single document to existing claim ──────────────────────────────
    st.divider()
    st.subheader("📤 Upload Document")
    uploaded = st.file_uploader("Add PDF to existing claim", type=["pdf"], key="pdf_uploader")
    if uploaded and st.button("🔄 Ingest", use_container_width=True):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        try:
            with st.spinner("Extracting and classifying..."):
                meta = ingestion_agent.ingest(tmp_path)
            # Save PDF permanently to data/<claim_id>/
            claim_dir = DATA_DIR / meta["claim_id"]
            claim_dir.mkdir(parents=True, exist_ok=True)
            dest = claim_dir / uploaded.name
            shutil.move(tmp_path, str(dest))
            # Re-upsert with correct filename path
            from src.tools.pdf_extractor import extract_text as _et
            store.add_document(
                claim_id=meta["claim_id"], file_type=meta["file_type"],
                text=_et(str(dest)), path=uploaded.name, summary="",
            )
            st.success(f"✅ **{meta['claim_id']}** / {meta['file_type']}")
            st.rerun()
        except Exception as e:
            st.error(f"Ingestion failed: {e}")
            if os.path.exists(tmp_path):
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

            # ── Sources analysed ─────────────────────────────────────────────
            docs_used = store.get_by_claim(claim_id)
            if docs_used:
                refs_html = " &nbsp;·&nbsp; ".join(
                    f'<span style="background:#e8f4f8;border:1px solid #b3d4f0;'
                    f'border-radius:4px;padding:2px 8px;font-size:0.8rem;color:#1565c0">'
                    f'📄 {claim_id} — {d["metadata"]["file_type"]}</span>'
                    for d in docs_used
                )
                st.markdown(
                    f'<div style="margin:8px 0 4px 0"><strong>Sources analysed:</strong> '
                    f'{refs_html}</div>',
                    unsafe_allow_html=True,
                )

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
    for msg_idx, msg in enumerate(st.session_state.messages):
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
            display_text = text.split("\n\n", 1)[-1] if text.startswith("[Context:") else text
            with st.chat_message("user"):
                st.markdown(display_text)
        elif role == "assistant" and text:
            with st.chat_message("assistant"):
                st.markdown(safe_md(text))
                # Render citations if this message has any
                saved = st.session_state.citations_by_msg.get(msg_idx, [])
                render_citations(saved, key_prefix=f"hist_{msg_idx}")

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
        current_citations: list = []
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            try:
                for chunk in chat_agent.stream_response(user_input, history, claim_id, current_citations):
                    full_response += chunk
                    response_placeholder.markdown(safe_md(full_response) + "▌")
                response_placeholder.markdown(safe_md(full_response))
            except Exception as e:
                st.error(f"Error: {e}")
                full_response = f"Error: {e}"

            # Show citations inline right after the response
            render_citations(current_citations, key_prefix="live")

        # Persist to history + save citations keyed by assistant message index
        st.session_state.messages.append({"role": "user", "content": user_input})
        assistant_idx = len(st.session_state.messages)  # index of the msg we're about to append
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        if current_citations:
            st.session_state.citations_by_msg[assistant_idx] = current_citations

    # Clear chat button
    if st.session_state.messages:
        if st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()
