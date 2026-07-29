import json
import anthropic
import pdfplumber
from src.config import ANTHROPIC_API_KEY, MODEL_SPECIALIST

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

EXTRACTION_SYSTEM = """You are an insurance document metadata extractor.
Extract structured metadata from insurance document text.
Return only valid JSON with no commentary."""


def extract_text(pdf_path: str) -> str:
    """Extract full text from a PDF file."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    return "\n\n".join(pages)


def classify_and_extract(text: str) -> dict:
    """Use claude-haiku to classify doc type and extract key metadata."""
    prompt = f"""Extract metadata from this insurance document text.

DOCUMENT TEXT:
{text[:3000]}

Return JSON with these fields (use null if not found):
{{
  "claim_id": "CLM-XXXXXXXX or null",
  "file_type": "one of: Policy, FNOL, Claimant Statement, Coverage Determination, Proof Of Loss, Adjuster Notes, Investigation Report, Reserve Analysis, Settlement Agreement, Payment Authorization, Final Settlement, Closure Summary, Reopening Notice, Other",
  "policy_id": "policy number or null",
  "insured_name": "company or person name or null",
  "date_of_loss": "date string or null",
  "claim_amount": "dollar amount as string or null",
  "cause_of_loss": "brief description or null"
}}"""

    response = client.messages.create(
        model=MODEL_SPECIALIST,
        max_tokens=512,
        system=[{"type": "text", "text": EXTRACTION_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": ["string", "null"]},
                    "file_type": {"type": "string"},
                    "policy_id": {"type": ["string", "null"]},
                    "insured_name": {"type": ["string", "null"]},
                    "date_of_loss": {"type": ["string", "null"]},
                    "claim_amount": {"type": ["string", "null"]},
                    "cause_of_loss": {"type": ["string", "null"]},
                },
                "required": ["claim_id", "file_type"],
                "additionalProperties": False,
            }
        }}
    )
    text_block = next(b for b in response.content if b.type == "text")
    return json.loads(text_block.text)
