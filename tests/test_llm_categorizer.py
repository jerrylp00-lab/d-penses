from unittest.mock import patch, MagicMock
import json
import pytest
from llm_categorizer import categorize_transactions, _build_prompt, _parse_response


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


def test_categorize_transactions_calls_api():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -112.0, "label": "ASSURANCE"}]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps([
            {"transaction_id": "t1", "category": "recurring", "confidence": 0.9}
        ])}}]
    }
    with patch("llm_categorizer.requests.post", return_value=mock_response):
        result = categorize_transactions(txs)
    assert len(result) == 1
    assert result[0]["category"] == "recurring"


def test_categorize_transactions_api_fail_returns_divers():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -50.0, "label": "MISC"}]
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server error"
    with patch("llm_categorizer.requests.post", return_value=mock_response):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "divers"
    assert result[0]["confidence"] == 0.0
