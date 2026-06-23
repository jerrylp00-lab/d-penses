from unittest.mock import patch, MagicMock
from llm_categorizer import categorize_transactions, CATEGORIES, _preprocess


def test_categories_are_personal_finance():
    expected = {"alimentation", "transport", "loisirs", "sante", "shopping", "abonnements", "virement", "divers"}
    assert set(CATEGORIES) == expected


def test_empty_input():
    assert categorize_transactions([]) == []


def test_preprocess_no_cheques():
    txs = [
        {"transaction_id": "1", "label": "CARREFOUR", "date": "2026-06-01", "amount": -42.0},
        {"transaction_id": "2", "label": "SNCF",      "date": "2026-06-02", "amount": -89.0},
    ]
    pre, to_llm = _preprocess(txs)
    assert pre == []
    assert len(to_llm) == 2


def test_fallback_on_llm_failure():
    txs = [{"transaction_id": "1", "label": "TEST", "date": "2026-06-01", "amount": -10.0}]
    with patch("llm_categorizer.requests.post", side_effect=Exception("network error")):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "divers"
    assert result[0]["transaction_id"] == "1"


def test_llm_result_mapped_by_id():
    txs = [{"transaction_id": "abc", "label": "Netflix", "date": "2026-06-01", "amount": -17.99}]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '[{"transaction_id": "abc", "category": "abonnements", "confidence": 0.95}]'}}]
    }
    with patch("llm_categorizer.requests.post", return_value=mock_resp):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "abonnements"
    assert result[0]["confidence"] == 0.95
