# ingest.py
import logging
from datetime import datetime, timezone

import config
from finary_auth import FinaryClient
from llm_categorizer import categorize_transactions
from sheets_client import SheetsClient

log = logging.getLogger("ingest")

# Patterns de libellé sur compte courant CA = prélèvement mensuel différé (double-compte avec carte)
_DIFFERE_PATTERNS = ["CARTE", "VISA"]


def _is_differe_line(label: str) -> bool:
    upper = label.upper()
    return any(p in upper for p in _DIFFERE_PATTERNS)


def _normalize_transaction(raw: dict, account_id: str, bank: str, tx_type: str, profile: str) -> dict:
    return {
        "transaction_id":  str(raw.get("id", "")),
        "date":            (raw.get("display_date") or raw.get("date", ""))[:10],
        "label":           raw.get("display_name") or raw.get("name") or "",
        "amount":          float(raw.get("value", 0)),
        "category":        "divers",
        "category_status": "pending",
        "confidence":      0.0,
        "profile":         profile,
        "account_id":      account_id,
        "bank":            bank,
        "type":            tx_type,
    }


def _deduplicate(rows: list[dict], existing_ids: set[str]) -> list[dict]:
    return [r for r in rows if r["transaction_id"] not in existing_ids]


def _dedup_batch(rows: list[dict]) -> list[dict]:
    """Remove intra-batch duplicates by transaction_id (same tx returned across multiple pages)."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        if r["transaction_id"] not in seen:
            seen.add(r["transaction_id"])
            out.append(r)
    return out


def _fetch_account_transactions(client: FinaryClient, account: dict, profile: str) -> list[dict]:
    account_id = account["id"]
    bank       = account["bank"]
    tx_type    = account["type"]
    is_differe_courant = account.get("differe", False) and tx_type == "courant"

    rows = []
    page = 1
    while True:
        batch = client.transactions(account_id, page=page, per_page=100)
        if not batch:
            break
        for raw in batch:
            label = raw.get("display_name") or raw.get("name") or ""
            if is_differe_courant and _is_differe_line(label):
                continue
            rows.append(_normalize_transaction(raw, account_id, bank, tx_type, profile))
        page += 1

    log.info(f"  {profile}/{bank}/{tx_type}: {len(rows)} transactions")
    return rows


def run_ingest():
    """Fetch all profiles from Finary, deduplicate against Sheets, categorize new rows, append."""
    sc     = SheetsClient(config.GOOGLE_SHEETS_ID, config.GOOGLE_SERVICE_ACCOUNT_JSON)
    client = FinaryClient()

    existing_ids = sc.get_existing_ids()
    log.info(f"Existing transactions in Sheets: {len(existing_ids)}")

    all_new_rows: list[dict] = []

    for profile_key, profile_cfg in config.PROFILES.items():
        log.info(f"Fetching profile: {profile_key}")
        for account in profile_cfg["accounts"]:
            rows = _fetch_account_transactions(client, account, profile_key)
            new  = _deduplicate(rows, existing_ids)
            all_new_rows.extend(new)
            existing_ids.update(r["transaction_id"] for r in new)

    all_new_rows = _dedup_batch(all_new_rows)

    if not all_new_rows:
        log.info("No new transactions.")
    else:
        log.info(f"Categorizing {len(all_new_rows)} new transactions...")
        categories = categorize_transactions(all_new_rows)
        cat_map    = {c["transaction_id"]: c for c in categories}
        for row in all_new_rows:
            cat = cat_map.get(row["transaction_id"], {})
            row["category"]        = cat.get("category", "divers")
            row["category_status"] = "confirmed"
            row["confidence"]      = float(cat.get("confidence", 0.0))

        sc.append_rows(all_new_rows)
        log.info(f"Appended {len(all_new_rows)} rows to Sheets.")

    sc.set_last_updated(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    log.info("Ingest complete.")
