"""SPEC-1 entry point.

Usage:
    python -m spec1_engine.main
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # loads .env from cwd if present

import uvicorn


def main() -> None:
    uvicorn.run(
        "spec1_engine.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
