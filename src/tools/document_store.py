import json
import re
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

from src.config import CHROMA_DIR, CHROMA_COLLECTION, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start += size - overlap
    return chunks


class DocumentStore:
    def __init__(self):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self._col = self._client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    def is_initialized(self) -> bool:
        return self._col.count() > 0

    def add_document(
        self,
        claim_id: str,
        file_type: str,
        text: str,
        path: str = "",
        summary: str = "",
        **extra,
    ) -> None:
        """Chunk and add a document to the store."""
        claim_id = claim_id or "UNKNOWN"
        chunks = _chunk_text(text)
        ids, texts, metas = [], [], []
        for i, chunk in enumerate(chunks):
            doc_id = f"{claim_id}__{re.sub(r'[^a-zA-Z0-9]', '_', file_type)}__{i}"
            ids.append(doc_id)
            texts.append(chunk)
            metas.append({
                "claim_id": claim_id,
                "file_type": file_type,
                "path": path,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "summary": summary[:500] if summary else "",
            })
        self._col.upsert(ids=ids, documents=texts, metadatas=metas)

    def search(
        self,
        query: str,
        claim_id: Optional[str] = None,
        n_results: int = 5,
    ) -> list[dict]:
        """Semantic search, optionally filtered to one claim."""
        where = {"claim_id": claim_id} if claim_id else None
        count = self._col.count()
        if count == 0:
            return []
        n = min(n_results, count)
        results = self._col.query(
            query_texts=[query],
            n_results=n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            out.append({"text": doc, "metadata": meta, "score": 1 - dist})
        return out

    def get_by_claim(self, claim_id: str) -> list[dict]:
        """Retrieve all documents for a claim (one entry per file_type)."""
        results = self._col.get(
            where={"claim_id": claim_id},
            include=["documents", "metadatas"],
        )
        # Deduplicate: keep first chunk per file_type for full-doc retrieval
        seen: dict[str, dict] = {}
        for doc, meta in zip(results["documents"], results["metadatas"]):
            ft = meta["file_type"]
            if ft not in seen or meta["chunk_index"] == 0:
                seen[ft] = {"text": doc, "metadata": meta}
        return list(seen.values())

    def list_claims(self) -> list[str]:
        """Return sorted list of all unique claim IDs."""
        results = self._col.get(include=["metadatas"])
        claims = {m["claim_id"] for m in results["metadatas"]}
        return sorted(claims)

    def initialize_from_json(self, json_path: Path) -> int:
        """Bulk-load claims_data.json into the store. Returns count added."""
        with open(json_path) as f:
            records = json.load(f)
        added = 0
        for rec in records:
            self.add_document(
                claim_id=rec.get("claim_id", "UNKNOWN"),
                file_type=rec.get("file_type", "Unknown"),
                text=rec.get("extracted_text", ""),
                path=rec.get("path", ""),
                summary=rec.get("summary", ""),
            )
            added += 1
        return added
