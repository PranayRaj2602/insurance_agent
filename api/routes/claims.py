import asyncio
import json
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from src.config import DATA_DIR, CLAIMS_METADATA_JSON
from src.tools.document_store import DocumentStore
from src.agents.ingestion import IngestionAgent
from src.agents.summarization import SummarizationAgent

router = APIRouter()

_store = DocumentStore()
_ingestion = IngestionAgent(_store)
_summarization = SummarizationAgent(_store)

_FILE_TYPE_MAP = {
    "fnol": "FNOL", "policy": "Policy",
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
}


def _load_meta() -> dict:
    if CLAIMS_METADATA_JSON.exists():
        return json.loads(CLAIMS_METADATA_JSON.read_text())
    return {}


def _save_meta(meta: dict):
    import os
    tmp = CLAIMS_METADATA_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, default=str))
    os.replace(tmp, CLAIMS_METADATA_JSON)


def _next_claim_id(existing: list) -> str:
    nums = [int(m.group(1)) for cid in existing
            if (m := re.match(r"CLM-(\d+)$", cid, re.IGNORECASE))]
    return f"CLM-{(max(nums) + 1) if nums else 1:08d}"


@router.get("")
def list_claims():
    claims = _store.list_claims()
    meta = _load_meta()
    return [
        {
            "id": cid,
            "insured_name": meta.get(cid, {}).get("insured_name"),
            "policy_id": meta.get(cid, {}).get("policy_id"),
            "date_of_loss": meta.get(cid, {}).get("date_of_loss"),
            "cause_of_loss": meta.get(cid, {}).get("cause_of_loss"),
            "doc_count": len(_store.get_by_claim(cid)),
            "is_new": cid in meta,
        }
        for cid in sorted(claims)
    ]


@router.get("/next-id")
def next_claim_id():
    existing = _store.list_claims()
    return {"id": _next_claim_id(existing)}


@router.get("/{claim_id}/documents")
def get_documents(claim_id: str):
    docs = _store.get_by_claim(claim_id)
    result = []
    for d in docs:
        raw_path = d["metadata"].get("path", "")
        filename = Path(raw_path).name  # strip any leading temp dir
        # Verify the file actually exists on disk; skip if not
        pdf_on_disk = DATA_DIR / claim_id / filename
        if not pdf_on_disk.exists():
            # Try to find any matching PDF by file_type slug
            ft_slug = re.sub(r"[^a-z0-9]+", "_", d["metadata"]["file_type"].lower()).strip("_")
            candidates = list((DATA_DIR / claim_id).glob(f"{ft_slug}*.pdf")) if (DATA_DIR / claim_id).exists() else []
            filename = candidates[0].name if candidates else filename
        result.append({
            "file_type": d["metadata"]["file_type"],
            "path": filename,
            "claim_id": claim_id,
        })
    return result


@router.post("")
async def create_claim(
    claim_id:     str = Form(...),
    insured_name: str = Form(""),
    policy_id:    str = Form(""),
    date_of_loss: str = Form(""),
    cause_of_loss: str = Form(""),
    files: list[UploadFile] = File(...),
):
    meta = _load_meta()
    if claim_id in _store.list_claims():
        raise HTTPException(400, f"{claim_id} already exists")

    claim_dir = DATA_DIR / claim_id
    claim_dir.mkdir(parents=True, exist_ok=True)
    ingested = []

    for uf in files:
        stem = re.sub(r"[_-]clm[-_]?\d+$", "", Path(uf.filename).stem, flags=re.IGNORECASE)
        hint = stem.replace("_", " ").replace("-", " ").title()
        hint = _FILE_TYPE_MAP.get(hint.lower(), hint)
        slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
        dest = claim_dir / f"{slug}_{claim_id}.pdf"
        dest.write_bytes(await uf.read())
        try:
            _ingestion.ingest_with_meta(str(dest), claim_id, hint, {
                "insured_name": insured_name, "policy_id": policy_id,
                "date_of_loss": date_of_loss, "cause_of_loss": cause_of_loss,
            })
            ingested.append(hint)
        except Exception as e:
            pass

    meta[claim_id] = {
        "insured_name": insured_name, "policy_id": policy_id,
        "date_of_loss": date_of_loss, "cause_of_loss": cause_of_loss,
        "created_at": datetime.now().isoformat(), "file_count": len(ingested),
    }
    _save_meta(meta)
    return {"claim_id": claim_id, "ingested": ingested}


@router.get("/{claim_id}/summarize")
async def summarize_claim(claim_id: str):
    """SSE stream: yields agent status events then final JSON summary."""
    async def event_stream():
        agents = [
            ("facts",    "🔍 Facts Agent (Haiku) — extracting claim facts..."),
            ("coverage", "📋 Coverage Agent (Haiku) — analyzing policy coverage..."),
            ("risk",     "⚠️ Risk Agent (Haiku) — assessing risk flags..."),
            ("timeline", "📅 Timeline Agent (Haiku) — building event sequence..."),
            ("synthesis","✍️ Synthesis Agent (Sonnet) — generating report..."),
        ]
        for key, msg in agents:
            yield f"data: {json.dumps({'type': 'status', 'agent': key, 'message': msg})}\n\n"
            await asyncio.sleep(0.05)

        try:
            result = await _summarization.summarize(claim_id)
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{claim_id}/ingest")
async def ingest_document(claim_id: str, file: UploadFile = File(...)):
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        meta = _ingestion.ingest(tmp_path)
        claim_dir = DATA_DIR / meta["claim_id"]
        claim_dir.mkdir(parents=True, exist_ok=True)
        dest = claim_dir / file.filename
        shutil.move(tmp_path, str(dest))
        return meta
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(500, str(e))
