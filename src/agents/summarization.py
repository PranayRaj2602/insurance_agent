import json
import asyncio
import anthropic

from src.config import ANTHROPIC_API_KEY, MODEL_SPECIALIST, MODEL_SYNTHESIS
from src.tools.document_store import DocumentStore

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# Stable system prompts — cached
_FACTS_SYSTEM = "You are an insurance claim facts extractor. Extract structured factual data from claim documents. Return valid JSON only."
_COVERAGE_SYSTEM = "You are an insurance coverage analyst. Extract coverage details and identify gaps. Return valid JSON only."
_RISK_SYSTEM = "You are an insurance risk assessor. Identify red flags, anomalies, and inconsistencies. Return valid JSON only."
_TIMELINE_SYSTEM = "You are an insurance claims timeline specialist. Build a chronological event sequence. Return valid JSON only."
_SYNTHESIS_SYSTEM = """You are a senior P&C insurance claim analyst. You receive structured analysis from four specialist agents and synthesize a comprehensive, professional claim summary. Write in clear, concise prose with structured sections."""


def _docs_to_text(docs: list[dict], max_chars: int = 6000) -> str:
    parts = []
    total = 0
    for d in docs:
        header = f"[{d['metadata']['file_type']}]"
        entry = f"{header}\n{d['text']}"
        if total + len(entry) > max_chars:
            break
        parts.append(entry)
        total += len(entry)
    return "\n\n---\n\n".join(parts)


async def _call_specialist(system: str, prompt: str, schema: dict) -> dict:
    response = await client.messages.create(
        model=MODEL_SPECIALIST,
        max_tokens=1024,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    text_block = next(b for b in response.content if b.type == "text")
    return json.loads(text_block.text)


class SummarizationAgent:
    def __init__(self, store: DocumentStore):
        self.store = store

    async def summarize(self, claim_id: str) -> dict:
        """Run 4 parallel specialist agents then synthesize."""
        docs = self.store.get_by_claim(claim_id)
        if not docs:
            return {"error": f"No documents found for {claim_id}"}

        doc_text = _docs_to_text(docs)

        facts, coverage, risk, timeline = await asyncio.gather(
            self._facts_agent(doc_text),
            self._coverage_agent(doc_text),
            self._risk_agent(doc_text),
            self._timeline_agent(doc_text),
        )

        summary_md = await self._synthesis_agent(claim_id, facts, coverage, risk, timeline)

        return {
            "claim_id": claim_id,
            "facts": facts,
            "coverage": coverage,
            "risk": risk,
            "timeline": timeline,
            "summary": summary_md,
        }

    async def _facts_agent(self, doc_text: str) -> dict:
        schema = {
            "type": "object",
            "properties": {
                "claim_id": {"type": ["string", "null"]},
                "policy_id": {"type": ["string", "null"]},
                "insured_name": {"type": ["string", "null"]},
                "date_of_loss": {"type": ["string", "null"]},
                "cause_of_loss": {"type": ["string", "null"]},
                "total_claimed": {"type": ["string", "null"]},
                "adjuster": {"type": ["string", "null"]},
                "document_types": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["claim_id", "document_types"],
            "additionalProperties": False,
        }
        return await _call_specialist(
            _FACTS_SYSTEM,
            f"Extract key facts from these claim documents:\n\n{doc_text[:4000]}",
            schema,
        )

    async def _coverage_agent(self, doc_text: str) -> dict:
        schema = {
            "type": "object",
            "properties": {
                "coverage_type": {"type": ["string", "null"]},
                "policy_period": {"type": ["string", "null"]},
                "building_limit": {"type": ["string", "null"]},
                "contents_limit": {"type": ["string", "null"]},
                "deductible": {"type": ["string", "null"]},
                "coverage_status": {"type": ["string", "null"]},
                "gaps_identified": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["coverage_status", "gaps_identified"],
            "additionalProperties": False,
        }
        return await _call_specialist(
            _COVERAGE_SYSTEM,
            f"Analyze coverage details from these claim documents:\n\n{doc_text[:4000]}",
            schema,
        )

    async def _risk_agent(self, doc_text: str) -> dict:
        schema = {
            "type": "object",
            "properties": {
                "overall_risk": {"type": "string", "enum": ["Low", "Medium", "High", "Unknown"]},
                "red_flags": {"type": "array", "items": {"type": "string"}},
                "anomalies": {"type": "array", "items": {"type": "string"}},
                "fraud_indicators": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": ["string", "null"]},
            },
            "required": ["overall_risk", "red_flags", "anomalies", "fraud_indicators"],
            "additionalProperties": False,
        }
        return await _call_specialist(
            _RISK_SYSTEM,
            f"Assess risk and identify red flags in these claim documents:\n\n{doc_text[:4000]}",
            schema,
        )

    async def _timeline_agent(self, doc_text: str) -> dict:
        schema = {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": ["string", "null"]},
                            "event": {"type": "string"},
                            "source": {"type": ["string", "null"]},
                        },
                        "required": ["event"],
                        "additionalProperties": False,
                    },
                },
                "claim_status": {"type": ["string", "null"]},
            },
            "required": ["events"],
            "additionalProperties": False,
        }
        return await _call_specialist(
            _TIMELINE_SYSTEM,
            f"Build a chronological event timeline from these claim documents:\n\n{doc_text[:4000]}",
            schema,
        )

    async def _synthesis_agent(
        self,
        claim_id: str,
        facts: dict,
        coverage: dict,
        risk: dict,
        timeline: dict,
    ) -> str:
        synthesis_prompt = f"""Synthesize a professional claim intelligence report for {claim_id}.

FACTS AGENT OUTPUT:
{json.dumps(facts, indent=2)}

COVERAGE AGENT OUTPUT:
{json.dumps(coverage, indent=2)}

RISK AGENT OUTPUT:
{json.dumps(risk, indent=2)}

TIMELINE AGENT OUTPUT:
{json.dumps(timeline, indent=2)}

Write a structured markdown report with these sections:
## Executive Summary
## Key Facts
## Coverage Analysis
## Risk Assessment
## Event Timeline
## Recommendations

Be concise, professional, and actionable."""

        response = await client.messages.create(
            model=MODEL_SYNTHESIS,
            max_tokens=8192,
            system=[{"type": "text", "text": _SYNTHESIS_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        return next(b.text for b in response.content if b.type == "text")
