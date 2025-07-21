import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from receipt.backend.app import app

client = TestClient(app)

def test_upload_txt():
    content = b"Amazon\n2024-01-01\n123.45\n"
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        f.write(content)
        f.flush()
        with open(f.name, 'rb') as file:
            response = client.post("/upload", files={"file": (os.path.basename(f.name), file, "text/plain")})
    os.unlink(f.name)
    assert response.status_code == 200
    data = response.json()
    assert data["vendor"] == "Amazon"
    assert data["amount"] == 123.45

def test_list_receipts():
    response = client.get("/receipts")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_aggregate():
    response = client.get("/aggregate")
    assert response.status_code == 200
    agg = response.json()
    assert "total" in agg
    assert "mean" in agg
    assert "median" in agg
    assert "mode" in agg 