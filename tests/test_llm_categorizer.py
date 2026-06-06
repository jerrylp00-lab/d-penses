from unittest.mock import patch, MagicMock
import json
import pytest
from llm_categorizer import categorize_transactions, _build_prompt, _parse_response, _preprocess


def test_build_prompt_contains_transactions():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -112.0, "label": "ASSURANCE HABITATION"}]
    prompt = _build_prompt(txs)
    assert "t1" in prompt
    assert "ASSURANCE HABITATION" in prompt


def test_parse_response_valid():
    raw = json.dumps([
        {"transaction_id": "t1", "category": "recurring", "confidence": 0.9}
    ])
    result = _parse_response(raw)
    assert result == [{"transaction_id": "t1", "category": "recurring", "confidence": 0.9}]


def test_parse_response_invalid_returns_empty():
    result = _parse_response("not json at all")
    assert result == []


def test_preprocess_cheque_chq():
    """Transactions with CHQ in label get travaux, confidence 1.0, not sent to LLM."""
    txs = [
        {"transaction_id": "t1", "date": "2026-06-01", "amount": -500.0, "label": "CHQ 1234567"},
        {"transaction_id": "t2", "date": "2026-06-01", "amount": -200.0, "label": "CHEQUE MARTIN PLOMBIER"},
        {"transaction_id": "t3", "date": "2026-06-01", "amount": -112.0, "label": "ASSURANCE HABITATION"},
    ]
    pre_categorized, to_llm = _preprocess(txs)
    assert len(pre_categorized) == 2
    assert all(r["category"] == "travaux" for r in pre_categorized)
    assert all(r["confidence"] == 1.0 for r in pre_categorized)
    assert len(to_llm) == 1
    assert to_llm[0]["transaction_id"] == "t3"


def test_preprocess_no_cheques():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -112.0, "label": "ASSURANCE"}]
    pre_categorized, to_llm = _preprocess(txs)
    assert pre_categorized == []
    assert len(to_llm) == 1


def test_categorize_transactions_cheque_bypass_llm():
    """CHQ transactions never reach the LLM."""
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -500.0, "label": "CHQ 999"}]
    with patch("llm_categorizer.requests.post") as mock_post:
        result = categorize_transactions(txs)
    mock_post.assert_not_called()
    assert result[0]["category"] == "travaux"
    assert result[0]["confidence"] == 1.0


def test_categorize_camca_pret_recurrent():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -423.5, "label": "CAMCA PRET MENSUALITE"}]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps([
            {"transaction_id": "t1", "category": "pret_recurrent", "confidence": 0.95}
        ])}}]
    }
    with patch("llm_categorizer.requests.post", return_value=mock_response):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "pret_recurrent"


def test_categorize_transactions_api_fail_returns_divers():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -50.0, "label": "MISC"}]
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server error"
    with patch("llm_categorizer.requests.post", return_value=mock_response):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "divers"
    assert result[0]["confidence"] == 0.0
