"""Unified server entrypoint.

This module re-exports the FastAPI app from app.py, ensuring that starting the
server via `uvicorn main:app` or `python main.py` serves the same routes as
`uvicorn app:app`.
"""

from app import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    # Use the app from app.py directly so hot reload works as expected
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)