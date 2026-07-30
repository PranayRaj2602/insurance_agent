from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.config import DATA_DIR

router = APIRouter()


@router.get("/{claim_id}/{filename}")
def serve_pdf(claim_id: str, filename: str):
    """Serve a PDF file directly — used by the React PDF viewer."""
    pdf_path = DATA_DIR / claim_id / filename
    if not pdf_path.exists():
        raise HTTPException(404, f"PDF not found: {claim_id}/{filename}")
    return FileResponse(str(pdf_path), media_type="application/pdf",
                        headers={"Content-Disposition": f"inline; filename={filename}"})
