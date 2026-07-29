import json
import anthropic
from typing import Optional

from src.config import ANTHROPIC_API_KEY, MODEL_SPECIALIST

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── Tool schemas for the chat orchestrator ────────────────────────────────────

TOOLS = [
    {
        "name": "search_documents",
        "description": (
            "Semantically search across all ingested insurance documents. "
            "Call this when answering questions about policy terms, claim details, "
            "coverage limits, deductibles, dates, or any factual question about claims. "
            "Optionally filter by claim_id to search within a single claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "claim_id": {
                    "type": "string",
                    "description": "Optional claim ID to restrict search (e.g. CLM-00000001)",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_claim_documents",
        "description": (
            "List all document types available for a specific claim. "
            "Use this to discover what documents exist before searching."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "Claim ID e.g. CLM-00000001"},
            },
            "required": ["claim_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_claim_summary",
        "description": (
            "Retrieve the pre-computed structured summary for a claim if one exists. "
            "Returns facts, coverage analysis, risk flags, and timeline."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "Claim ID e.g. CLM-00000001"},
            },
            "required": ["claim_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analyze_coverage",
        "description": (
            "Run a deep coverage gap analysis for a claim. Compares claim documents "
            "against policy terms to identify coverage issues, deductible mismatches, "
            "and potential underpayments. Spawns a specialist sub-agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {"type": "string", "description": "Claim ID to analyze"},
            },
            "required": ["claim_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "compare_claims",
        "description": (
            "Compare two claims side by side. Useful for identifying patterns, "
            "inconsistencies, or differences in how similar claims were handled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id_1": {"type": "string", "description": "First claim ID"},
                "claim_id_2": {"type": "string", "description": "Second claim ID"},
            },
            "required": ["claim_id_1", "claim_id_2"],
            "additionalProperties": False,
        },
    },
]


def execute_tool(
    name: str,
    inputs: dict,
    store,
    summaries_cache: dict,
    citations=None,
) -> str:
    """Execute a tool call and return a string result.
    If citations list is provided, search_documents appends citation metadata to it.
    """
    if name == "search_documents":
        results = store.search(
            query=inputs["query"],
            claim_id=inputs.get("claim_id"),
            n_results=5,
        )
        if not results:
            return "No documents found matching your query."
        parts = []
        for r in results:
            meta = r["metadata"]
            parts.append(
                f"[{meta['claim_id']} / {meta['file_type']}] (score: {r['score']:.2f})\n{r['text']}"
            )
            # Collect citation for UI display
            if citations is not None:
                citations.append({
                    "claim_id": meta["claim_id"],
                    "file_type": meta["file_type"],
                    "score": r["score"],
                    "text": r["text"],
                    "path": meta.get("path", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                })
        return "\n\n---\n\n".join(parts)

    elif name == "get_claim_documents":
        claim_id = inputs["claim_id"]
        docs = store.get_by_claim(claim_id)
        if not docs:
            return f"No documents found for {claim_id}."
        types = [d["metadata"]["file_type"] for d in docs]
        return f"Documents for {claim_id}: {', '.join(types)}"

    elif name == "get_claim_summary":
        claim_id = inputs["claim_id"]
        if claim_id in summaries_cache:
            s = summaries_cache[claim_id]
            return f"## Summary for {claim_id}\n\n{s.get('summary', 'No summary text.')}"
        return f"No pre-computed summary for {claim_id}. Use the Summarize tab to generate one first."

    elif name == "analyze_coverage":
        cid = inputs["claim_id"]
        if citations is not None:
            for d in store.get_by_claim(cid):
                citations.append({
                    "claim_id": cid,
                    "file_type": d["metadata"]["file_type"],
                    "score": 1.0,
                    "text": d["text"][:200],
                    "path": d["metadata"].get("path", ""),
                    "chunk_index": 0,
                })
        return _coverage_sub_agent(cid, store)

    elif name == "compare_claims":
        cid1, cid2 = inputs["claim_id_1"], inputs["claim_id_2"]
        if citations is not None:
            for cid in (cid1, cid2):
                for d in store.get_by_claim(cid)[:3]:
                    citations.append({
                        "claim_id": cid,
                        "file_type": d["metadata"]["file_type"],
                        "score": 1.0,
                        "text": d["text"][:200],
                        "path": d["metadata"].get("path", ""),
                        "chunk_index": 0,
                    })
        return _compare_sub_agent(cid1, cid2, store)

    return f"Unknown tool: {name}"


def _coverage_sub_agent(claim_id: str, store) -> str:
    """Specialist sub-agent: coverage gap analysis."""
    docs = store.get_by_claim(claim_id)
    if not docs:
        return f"No documents found for {claim_id}."

    policy_docs = [d for d in docs if "policy" in d["metadata"]["file_type"].lower()]
    claim_docs = [d for d in docs if "policy" not in d["metadata"]["file_type"].lower()]

    policy_text = "\n\n".join(d["text"] for d in policy_docs) if policy_docs else "No policy document found."
    claim_text = "\n\n".join(
        f"[{d['metadata']['file_type']}]\n{d['text']}" for d in claim_docs[:5]
    )

    response = client.messages.create(
        model=MODEL_SPECIALIST,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": "You are a P&C insurance coverage analyst. Identify coverage gaps, deductible issues, and policy compliance problems.",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"""Analyze coverage for claim {claim_id}.

POLICY:
{policy_text[:2000]}

CLAIM DOCUMENTS:
{claim_text[:2000]}

Provide:
1. Coverage status (covered/partial/excluded)
2. Applicable deductible vs. claimed amount
3. Any coverage gaps or concerns
4. Recommendation""",
        }],
    )
    return next(b.text for b in response.content if b.type == "text")


def _compare_sub_agent(claim_id_1: str, claim_id_2: str, store) -> str:
    """Specialist sub-agent: claim comparison."""
    docs1 = store.get_by_claim(claim_id_1)
    docs2 = store.get_by_claim(claim_id_2)

    def summarize_claim(claim_id, docs):
        types = [d["metadata"]["file_type"] for d in docs]
        text = "\n".join(d["text"][:400] for d in docs[:4])
        return f"Claim {claim_id} ({', '.join(types)}):\n{text}"

    summary1 = summarize_claim(claim_id_1, docs1) if docs1 else f"{claim_id_1}: No documents."
    summary2 = summarize_claim(claim_id_2, docs2) if docs2 else f"{claim_id_2}: No documents."

    response = client.messages.create(
        model=MODEL_SPECIALIST,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": "You are an insurance claims analyst. Compare claims objectively and identify key differences.",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"""Compare these two insurance claims:

{summary1}

---

{summary2}

Compare: claim type, severity, coverage applied, settlement status, and any notable differences.""",
        }],
    )
    return next(b.text for b in response.content if b.type == "text")
