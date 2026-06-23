import pytest
from ingest import _normalize_transaction, _is_differe_line, _deduplicate


def test_normalize_transaction_basic():
    raw = {
        "id": "tx123",
        "display_date": "2026-06-15T00:00:00",
        "value": -42.5,
        "display_name": "CARREFOUR CITY",
        "name": "CARREFOUR",
    }
    result = _normalize_transaction(raw, account_id="acc1", bank="CA", tx_type="carte", profile="jeremy")
    assert result["transaction_id"] == "tx123"
    assert result["date"] == "2026-06-15"
    assert result["amount"] == -42.5
    assert result["label"] == "CARREFOUR CITY"
    assert result["profile"] == "jeremy"
    assert result["bank"] == "CA"
    assert result["type"] == "carte"
    assert result["category"] == "divers"
    assert result["category_status"] == "pending"


def test_normalize_transaction_fallback_name():
    raw = {"id": "tx1", "date": "2026-06-01", "value": -10.0, "name": "SNCF"}
    result = _normalize_transaction(raw, account_id="acc1", bank="Bourso", tx_type="courant", profile="manon")
    assert result["label"] == "SNCF"
    assert result["date"] == "2026-06-01"


def test_is_differe_line_detects_carte():
    assert _is_differe_line("CARTE VISA DEBIT MENSUEL") is True
    assert _is_differe_line("REMB CARTE FEVRIER") is True


def test_is_differe_line_detects_visa():
    assert _is_differe_line("VISA PREMIER PRELEVEMENT") is True


def test_is_differe_line_ignores_normal():
    assert _is_differe_line("CARREFOUR CITY") is False
    assert _is_differe_line("SNCF BILLET") is False
    assert _is_differe_line("NETFLIX") is False


def test_deduplicate_removes_known_ids():
    rows = [
        {"transaction_id": "a", "amount": -10},
        {"transaction_id": "b", "amount": -20},
        {"transaction_id": "c", "amount": -30},
    ]
    existing = {"a", "c"}
    result = _deduplicate(rows, existing)
    assert len(result) == 1
    assert result[0]["transaction_id"] == "b"


def test_deduplicate_empty_existing():
    rows = [{"transaction_id": "x", "amount": -5}]
    result = _deduplicate(rows, set())
    assert len(result) == 1


def test_deduplicate_all_known():
    rows = [{"transaction_id": "a"}, {"transaction_id": "b"}]
    result = _deduplicate(rows, {"a", "b"})
    assert result == []
