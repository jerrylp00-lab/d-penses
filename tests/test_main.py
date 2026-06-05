from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def mock_deps():
    """Patch Airtable and Finary so tests don't hit real APIs."""
    with patch("main.AirtableClient") as MockAirtable, \
         patch("main.FinaryClient") as MockFinary:

        mock_at = MagicMock()
        MockAirtable.return_value = mock_at
        mock_at.get_last_updated.return_value = __import__("datetime").datetime(2026, 6, 6)
        mock_at.get_cash.return_value = 3100.0
        mock_at.get_transactions.return_value = [
            {"record_id": "rec1", "transaction_id": "t1", "date": "2026-06-01",
             "amount": 690.0, "label": "LOYER DUPONT", "category": "loyer",
             "category_status": "confirmed", "confidence": 0.95},
            {"record_id": "rec2", "transaction_id": "t2", "date": "2026-06-01",
             "amount": -112.0, "label": "ASSURANCE HABITATION", "category": "recurring",
             "category_status": "pending", "confidence": 0.85},
        ]

        mock_finary = MagicMock()
        MockFinary.return_value = mock_finary

        yield mock_at, mock_finary


@pytest.fixture
def client(mock_deps):
    from main import app
    return TestClient(app)


def test_dashboard_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SCI" in resp.text


def test_confirm_category(client, mock_deps):
    mock_at, _ = mock_deps
    resp = client.post("/validate/t1", json={"category": "loyer", "status": "confirmed"})
    assert resp.status_code == 200
    mock_at.update_category.assert_called_once_with("t1", "loyer", "confirmed")


def test_reject_category(client, mock_deps):
    mock_at, _ = mock_deps
    resp = client.post("/validate/t2", json={"category": "divers", "status": "rejected"})
    assert resp.status_code == 200
    mock_at.update_category.assert_called_once_with("t2", "divers", "rejected")
