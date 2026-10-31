"""Write the API contract to documentation/api/openapi.json.

Run after changing schemas.py or a route: .venv/bin/python export_openapi.py
"""

import json
from pathlib import Path

from app import app

OUT = Path(__file__).parent.parent.parent / "documentation" / "api" / "openapi.json"

if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {OUT}")
