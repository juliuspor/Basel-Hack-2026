"""Guards the seams between the teams. Run: .venv/bin/python -m pytest"""

import json
from pathlib import Path

import pytest
from PIL import Image

from app import app
from providers import PROVIDERS, make_provider, privacy_mask
from schemas import AreaDetail
from storage import LocalAssetStore

ROOT = Path(__file__).parents[3]
SPEC = ROOT / "documentation" / "api" / "openapi.json"
DEMO = ROOT / "code" / "ios" / "BikeSlot" / "Demo" / "demo-areas.json"


def test_spec_is_up_to_date():
    """documentation/api/openapi.json must match the code; rerun export_openapi.py."""
    assert json.loads(SPEC.read_text()) == app.openapi()


def test_app_demo_data_matches_contract():
    """The iOS demo data must still decode as the current API; rerun code/ios/refresh-demo.sh."""
    for area in json.loads(DEMO.read_text()):
        AreaDetail.model_validate(area)


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        make_provider("nope")


@pytest.mark.parametrize("name", ["diff"])
def test_provider_reads_rendered_frames(name):
    """A provider must get every slot right on a simulated morning."""
    assets = LocalAssetStore()
    cameras = assets.scene_out / "cameras"
    if not cameras.exists():
        pytest.skip("run code/scene-generator/build_all.sh first")
    provider = PROVIDERS[name]()
    for folder in sorted(cameras.iterdir()):
        camera = assets.camera(folder.name)
        for frame in camera["frames"][::3]:
            image = Image.open(folder / frame["file"]).convert("RGB")
            result = provider.analyze(privacy_mask(image, camera["area_roi"]), camera)
            assert result.occupied == set(frame["occupied"]), (folder.name, frame["time"])


def test_spot_without_camera_is_listed_but_not_analysed():
    """A mapped spot with no calibrated camera shows its slots as unknown and refuses frames."""
    if not (LocalAssetStore().scene_out / "cameras").exists():
        pytest.skip("run code/scene-generator/build_all.sh first")
    from fastapi.testclient import TestClient

    client = TestClient(app)
    spots = {area["id"]: area for area in client.get("/areas").json()}
    garage = spots["bike-garage-north"]
    assert garage["kind"] == "bike_garage" and garage["capacity"] == 48 and garage["updated_at"] is None
    assert client.post("/ingest/bike-garage-north", content=b"\xff\xd8").status_code == 409
