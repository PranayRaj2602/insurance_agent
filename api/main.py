import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import claims, chat, documents

app = FastAPI(title="Insurance Intelligence API", version="1.0.0")

# Allow localhost in dev; in prod the same origin serves everything
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router,    prefix="/api/claims",    tags=["claims"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ── Serve React build in production ──────────────────────────────────────────
# React build output lands in frontend/dist after `npm run build`
DIST = Path(__file__).parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_react(full_path: str):
        """Catch-all: return index.html so React Router handles navigation."""
        index = DIST / "index.html"
        return FileResponse(str(index))
