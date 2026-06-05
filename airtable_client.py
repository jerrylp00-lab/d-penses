# airtable_client.py
from datetime import datetime
from typing import Optional
from pyairtable import Api
import config


class AirtableClient:
    def __init__(self):
        api = Api(config.AIRTABLE_API_KEY)
        base = api.base(config.AIRTABLE_BASE_ID)
        self._transactions = base.table(config.AIRTABLE_TRANSACTIONS_TABLE)
        self._metadata     = base.table(config.AIRTABLE_METADATA_TABLE)

    # ── Metadata ───────────────────────────────────────────────────────────────

    def get_last_updated(self) -> datetime:
        rows = self._metadata.all(formula="{key}='last_updated'")
        if not rows:
            return datetime(2000, 1, 1)
        value = rows[0]["fields"].get("value", "2000-01-01T00:00:00")
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime(2000, 1, 1)

    def set_last_updated(self, dt: Optional[datetime] = None):
        dt = dt or datetime.utcnow()
        value = dt.isoformat()
        rows = self._metadata.all(formula="{key}='last_updated'")
        if rows:
            self._metadata.update(rows[0]["id"], {"value": value})
        else:
            self._metadata.create({"key": "last_updated", "value": value})

    def set_cash(self, amount: float):
        rows = self._metadata.all(formula="{key}='cash'")
        value = str(round(amount, 2))
        if rows:
            self._metadata.update(rows[0]["id"], {"value": value})
        else:
            self._metadata.create({"key": "cash", "value": value})

    def get_cash(self) -> Optional[float]:
        rows = self._metadata.all(formula="{key}='cash'")
        if not rows:
            return None
        try:
            return float(rows[0]["fields"]["value"])
        except (KeyError, ValueError):
            return None

    # ── Transactions ───────────────────────────────────────────────────────────

    def get_transactions(self) -> list[dict]:
        rows = self._transactions.all(sort=["date"])
        result = []
        for r in rows:
            f = r["fields"]
            result.append({
                "record_id":       r["id"],
                "transaction_id":  f.get("transaction_id", ""),
                "date":            f.get("date", ""),
                "amount":          float(f.get("amount", 0)),
                "label":           f.get("label", ""),
                "category":        f.get("category", "divers"),
                "category_status": f.get("category_status", "pending"),
                "confidence":      float(f.get("confidence", 0)),
            })
        return result

    def upsert_transactions(self, transactions: list[dict]):
        """Insert new transactions; skip existing (by transaction_id)."""
        existing_ids = {
            r["fields"].get("transaction_id")
            for r in self._transactions.all(fields=["transaction_id"])
        }
        new = [t for t in transactions if t["transaction_id"] not in existing_ids]
        for tx in new:
            self._transactions.create({
                "transaction_id":  tx["transaction_id"],
                "date":            tx["date"],
                "amount":          tx["amount"],
                "label":           tx["label"],
                "category":        tx.get("category", "divers"),
                "category_status": tx.get("category_status", "pending"),
                "confidence":      tx.get("confidence", 0.0),
            })

    def update_category(self, transaction_id: str, category: str, status: str):
        rows = self._transactions.all(
            formula=f"{{transaction_id}}='{transaction_id}'"
        )
        if not rows:
            raise ValueError(f"Transaction {transaction_id} not found")
        self._transactions.update(rows[0]["id"], {
            "category":        category,
            "category_status": status,
        })
