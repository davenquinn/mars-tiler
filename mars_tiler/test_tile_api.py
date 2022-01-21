"""
Tests for tiling APIs. These must run after the database setup and image ingestion tests.
"""
from fastapi.testclient import TestClient
from .app import app
from pytest import fixture
from .test_database import test_datasets
from sparrow.utils import get_logger

log = get_logger(__name__)


@fixture(scope="session")
def client(test_datasets):
    return TestClient(app)


class TestTileAPI:
    def test_tile_api_exists(self, client):
        response = client.get("/healthcheck")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_elevation_mosaic(self, client):
        response = client.get("/elevation-mosaic")
        assert response.status_code == 200
        mosaics = response.json()["mosaic"]
        assert len(mosaics) == 1
        assert mosaics[0] == "elevation_model"

    def test_get_datasets(self, client):
        response = client.get("/elevation-mosaic/assets")
        assert response.status_code == 200
        data = response.json()
        assert len(data["features"]) == 3

    def test_get_tile(self, client, db):
        tile_address = dict(z=8, x=234, y=130)
        response = client.get(
            "/elevation-mosaic/tiles/{z}/{x}/{y}.png".format(**tile_address),
            params=dict(use_cache=False),
        )
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/png"
        assets = response.headers["X-Assets"]
        assert assets != ""
        asset_list = assets.split(",")
        assert len(asset_list) >= 2
        res = db.session.execute(
            "SELECT (imagery.get_datasets(:x,:y,:z, :mosaics)).*",
            dict(**tile_address, mosaics=["elevation_model"]),
        ).all()
        assert len(res) == len(asset_list)
        log.info(response.headers["Server-Timing"])

    def test_tile_set_cache(self, client, db):
        tile_address = dict(z=8, x=234, y=130)
        response = client.get(
            "/elevation-mosaic/tiles/{z}/{x}/{y}.png".format(**tile_address),
        )
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/png"
        assert response.headers["X-Tile-Cache"] == "miss"
        log.info(response.headers["Server-Timing"])

    def test_tile_get_cached(self, client, db):
        tile_address = dict(z=8, x=234, y=130)
        response = client.get(
            "/elevation-mosaic/tiles/{z}/{x}/{y}.png".format(**tile_address),
        )
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/png"
        assert response.headers["X-Tile-Cache"] == "hit"
        log.info(response.headers["Server-Timing"])
