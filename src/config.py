import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CLAIMS_JSON = DATA_DIR / "claims_data.json"
CLAIMS_METADATA_JSON = DATA_DIR / "claims_metadata.json"
CHROMA_DIR = DATA_DIR / ".chroma"

MODEL_ORCHESTRATOR = "claude-opus-4-8"
MODEL_SPECIALIST = "claude-haiku-4-5"
MODEL_SYNTHESIS = "claude-sonnet-4-6"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHROMA_COLLECTION = "insurance_docs"

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200
RETRIEVAL_TOP_K = 5
