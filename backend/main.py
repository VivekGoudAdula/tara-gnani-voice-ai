"""Vercel entrypoint re-exporting the FastAPI app instance."""
from app.main import app

__all__ = ["app"]

