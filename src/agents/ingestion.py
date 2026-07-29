import anthropic
from src.config import ANTHROPIC_API_KEY
from src.tools.pdf_extractor import extract_text, classify_and_extract
from src.tools.document_store import DocumentStore

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


class IngestionAgent:
    def __init__(self, store: DocumentStore):
        self.store = store

    def ingest(self, pdf_path: str) -> dict:
        """Extract, classify, and store a PDF document."""
        text = extract_text(pdf_path)
        if not text.strip():
            raise ValueError(f"Could not extract text from {pdf_path}")

        metadata = classify_and_extract(text)

        # Use filename as fallback claim_id if LLM couldn't find one
        if not metadata.get("claim_id"):
            import re
            from pathlib import Path
            fname = Path(pdf_path).stem
            match = re.search(r"CLM-\d+", fname, re.IGNORECASE)
            metadata["claim_id"] = match.group(0).upper() if match else "UNKNOWN"

        self.store.add_document(
            claim_id=metadata["claim_id"],
            file_type=metadata.get("file_type", "Unknown"),
            text=text,
            path=str(pdf_path),
            summary="",
        )

        return {
            "claim_id": metadata["claim_id"],
            "file_type": metadata.get("file_type", "Unknown"),
            "policy_id": metadata.get("policy_id"),
            "insured_name": metadata.get("insured_name"),
            "date_of_loss": metadata.get("date_of_loss"),
            "claim_amount": metadata.get("claim_amount"),
            "cause_of_loss": metadata.get("cause_of_loss"),
            "text_length": len(text),
        }
