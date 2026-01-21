# serve_frontend.py
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# IMPORTANT: we import your existing app
from evaluator.app import app as api_app

# Wrap the existing app (so routes stay the same)
app = api_app

# If frontend is built, serve it from / (root)
dist_dir = Path(__file__).parent / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(dist_dir / "index.html")
