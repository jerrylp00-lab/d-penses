# tests/test_airtable_client.py
from unittest.mock import MagicMock, patch
import pytest
from airtable_client import AirtableClient


@pytest.fixture
def client():
    with patch("airtable_client.Api") as MockApi:
        mock_api = MagicMock()
        MockApi.return_value = mock_api
        c = AirtableClient.__new__(AirtableClient)
        c._transactions = MagicMock()
        c._metadata     = MagicMock()
        yield c


def test_get_last_updated_returns_datetime(client):
    from datetime import datetime
    client._metadata.all.return_value = [
        {"fields": {"key": "last_updated", "value": "2026-01-01T12:00:00"}}
    ]
    result = client.get_last_updated()
    assert isinstance(result, datetime)
    assert result.year == 2026


def test_get_last_updated_missing_returns_epoch(client):
    from datetime import datetime
    client._metadata.all.return_value = []
    result = client.get_last_updated()
    assert result == datetime(2000, 1, 1)


def test_upsert_transactions_calls_create(client):
    txs = [{"transaction_id": "t1", "date": "2026-06-01",
             "amount": 690.0, "label": "LOYER DUPONT"}]
    client._transactions.all.return_value = []  # no existing
    client.upsert_transactions(txs)
    client._transactions.batch_create.assert_called_once()


def test_upsert_transactions_skips_duplicates(client):
    """Dedup: existing transaction_id is not re-inserted."""
    existing = [{"fields": {"transaction_id": "t1"}}]
    client._transactions.all.return_value = existing
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": 690.0, "label": "LOYER"}]
    client.upsert_transactions(txs)
    client._transactions.batch_create.assert_not_called()


def test_update_category_raises_on_unknown_id(client):
    """ValueError raised when transaction_id not found."""
    client._transactions.all.return_value = []
    with pytest.raises(ValueError, match="not found"):
        client.update_category("nonexistent", "divers", "confirmed")


def test_get_transactions_returns_list(client):
    client._transactions.all.return_value = [
        {"id": "rec1", "fields": {
            "transaction_id": "t1", "date": "2026-06-01",
            "amount": 690.0, "label": "LOYER", "category": "loyer",
            "category_status": "confirmed", "confidence": 0.95
        }}
    ]
    result = client.get_transactions()
    assert len(result) == 1
    assert result[0]["transaction_id"] == "t1"


def test_update_category_status(client):
    client._transactions.all.return_value = [
        {"id": "rec1", "fields": {"transaction_id": "t1"}}
    ]
    client.update_category("t1", category="loyer", status="confirmed")
    client._transactions.update.assert_called_once_with(
        "rec1", {"category": "loyer", "category_status": "confirmed"}
    )
