# sheets_client.py
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TRANSACTIONS_WS = "transactions"
METADATA_WS = "metadata"
HEADER = [
    "transaction_id", "date", "label", "amount",
    "category", "category_status", "confidence",
    "profile", "account_id", "bank", "type",
]


class SheetsClient:
    def __init__(self, sheet_id: str, service_account_path: str):
        creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        self._txs  = spreadsheet.worksheet(TRANSACTIONS_WS)
        self._meta = spreadsheet.worksheet(METADATA_WS)

    def get_existing_ids(self) -> set[str]:
        records = self._txs.get_all_records()
        return {r["transaction_id"] for r in records if r.get("transaction_id")}

    def append_rows(self, rows: list[dict]):
        if not rows:
            return
        values = [[r[k] for k in HEADER] for r in rows]
        self._txs.append_rows(values, value_input_option="RAW")

    def get_transactions(self, profile: str | None = None) -> list[dict]:
        records = self._txs.get_all_records()
        if profile and profile != "commun":
            return [r for r in records if r.get("profile") == profile]
        return records

    def get_last_updated(self) -> str | None:
        records = self._meta.get_all_records()
        for r in records:
            if r.get("key") == "last_updated":
                return r.get("value") or None
        return None

    def set_last_updated(self, iso_dt: str):
        records = self._meta.get_all_records()
        for i, r in enumerate(records):
            if r.get("key") == "last_updated":
                self._meta.update_cell(i + 2, 2, iso_dt)
                return
        self._meta.append_row(["last_updated", iso_dt])
