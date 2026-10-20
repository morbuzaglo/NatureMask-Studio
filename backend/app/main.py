"""NatureMask Studio — local FastAPI application (serves the built frontend and the /api)."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .storage.projects import data_dir

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST = os.path.join(ROOT, "frontend", "dist")


def _setup_logging():
    os.makedirs(os.path.join(data_dir(), "logs"), exist_ok=True)
    h = RotatingFileHandler(os.path.join(data_dir(), "logs", "naturemask.log"), maxBytes=2_000_000, backupCount=3,
                            encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("naturemask")
    root.setLevel(logging.INFO)
    if not root.handlers:
        root.addHandler(h)
        root.addHandler(logging.StreamHandler())


_setup_logging()
app = FastAPI(title="NatureMask Studio API", version="0.1.0",
              description="Local, offline API. No data leaves this computer.")
app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logging.getLogger("naturemask").exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"detail": f"Internal error: {exc}"}, status_code=500)


if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = os.path.join(DIST, path)
        if path and os.path.isfile(f):
            return FileResponse(f)
        return FileResponse(os.path.join(DIST, "index.html"))
