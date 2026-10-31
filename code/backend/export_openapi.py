"""Writes the OpenAPI specs of both APIs to documentation/api/.

Run from code/backend after changing a route or a response model:
    .venv/bin/python export_openapi.py
"""

import json
from pathlib import Path

import composition

TARGET = Path(__file__).parents[2] / "documentation" / "api"


def main() -> None:
    TARGET.mkdir(exist_ok=True)
    for name, app in [("ingest", composition.ingest_app()), ("availability", composition.availability_app())]:
        path = TARGET / f"{name}.openapi.json"
        path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
