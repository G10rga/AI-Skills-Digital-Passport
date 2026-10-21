"""Run the BTU AI Skills Digital Passport backend.

In PyCharm: right-click this file -> Run 'run'
(or Debug 'run' to hit breakpoints in app/).

Then open http://127.0.0.1:8000/docs

Settings can be overridden with environment variables (HOST, PORT) —
see .env.example for the full list.
"""

import os
import sys
from pathlib import Path

# Make `app` importable and relative paths predictable no matter
# what working directory PyCharm launches this from.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"BTU AI Skills Digital Passport API -> http://{host}:{port}/docs")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,  # debugger-friendly; use --reload only from the CLI
    )


if __name__ == "__main__":
    main()
