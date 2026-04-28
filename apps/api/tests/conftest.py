import pytest
from fastapi.testclient import TestClient

from golf_api.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(env="test")
    return TestClient(app)
