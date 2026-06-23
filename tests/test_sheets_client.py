from unittest.mock import MagicMock, patch
import pytest
from sheets_client import SheetsClient, HEADER


@pytest.fixture
def mock_sheet():
    with patch("sheets_client.gspread") as mock_gspread, \
         patch("sheets_client.Credentials") as mock_creds:

        mock_ws_txs = MagicMock()
        mock_ws_meta = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.worksheet.side_effect = lambda name: (
            mock_ws_txs if name == "transactions" else mock_ws_meta
        )
        mock_gspread.authorize.return_value.open_by_key.return_value = mock_spreadsheet

        client = SheetsClient(sheet_id="FAKE_ID", service_account_path="fake.json")
        yield client, mock_ws_txs, mock_ws_meta


def test_get_existing_ids_empty(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = []
    assert client.get_existing_ids() == set()


def test_get_existing_ids_with_data(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "abc", "date": "2026-06-01"},
        {"transaction_id": "def", "date": "2026-06-02"},
    ]
    assert client.get_existing_ids() == {"abc", "def"}


def test_append_rows_calls_worksheet(mock_sheet):
    client, ws_txs, _ = mock_sheet
    rows = [
        {
            "transaction_id": "abc", "date": "2026-06-01", "label": "Carrefour",
            "amount": -42.5, "category": "alimentation", "category_status": "confirmed",
            "confidence": 0.9, "profile": "jeremy", "account_id": "acc1",
            "bank": "CA", "type": "carte",
        }
    ]
    client.append_rows(rows)
    ws_txs.append_rows.assert_called_once()
    values = ws_txs.append_rows.call_args[0][0]
    assert values[0][0] == "abc"
    assert values[0][3] == -42.5


def test_append_rows_empty_does_nothing(mock_sheet):
    client, ws_txs, _ = mock_sheet
    client.append_rows([])
    ws_txs.append_rows.assert_not_called()


def test_get_transactions_all(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "a", "profile": "jeremy", "amount": -10},
        {"transaction_id": "b", "profile": "manon", "amount": -20},
        {"transaction_id": "c", "profile": "commun", "amount": -30},
    ]
    result = client.get_transactions()
    assert len(result) == 3


def test_get_transactions_by_profile(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "a", "profile": "jeremy", "amount": -10},
        {"transaction_id": "b", "profile": "manon", "amount": -20},
    ]
    result = client.get_transactions(profile="jeremy")
    assert len(result) == 1
    assert result[0]["transaction_id"] == "a"


def test_get_transactions_commun_returns_all(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "a", "profile": "jeremy"},
        {"transaction_id": "b", "profile": "manon"},
        {"transaction_id": "c", "profile": "commun"},
    ]
    result = client.get_transactions(profile="commun")
    assert len(result) == 3


def test_get_last_updated_found(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = [{"key": "last_updated", "value": "2026-06-20T06:00:00"}]
    assert client.get_last_updated() == "2026-06-20T06:00:00"


def test_get_last_updated_not_found(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = []
    assert client.get_last_updated() is None


def test_set_last_updated_updates_existing(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = [{"key": "last_updated", "value": "old"}]
    client.set_last_updated("2026-06-23T06:00:00")
    ws_meta.update_cell.assert_called_once_with(2, 2, "2026-06-23T06:00:00")


def test_set_last_updated_appends_if_missing(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = []
    client.set_last_updated("2026-06-23T06:00:00")
    ws_meta.append_row.assert_called_once_with(["last_updated", "2026-06-23T06:00:00"])
