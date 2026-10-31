"""Both APIs and the MCP server on a laptop, sharing one in-memory store.

Run from code/backend:
    .venv/bin/uvicorn local:app --port 8000
"""

import composition
import logs

logs.configure()
app = composition.local_app()
