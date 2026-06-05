# main.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from airtable_client import AirtableClient
from finary_auth import FinaryClient
from llm_categorizer import categorize_transactions
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("main")

app       = FastAPI(title="SCI Dashboard")
templates = Jinja2Templates(directory="templates")


# ── Pydantic models ────────────────────────────────────────────────────────────

class ValidatePayload(BaseModel):
    category: str
    status: str  # "confirmed" | "rejected"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_stale(last_updated: datetime) -> bool:
    return (datetime.now(timezone.utc).replace(tzinfo=None) - last_updated) > timedelta(days=config.CACHE_TTL_DAYS)


def _fetch_and_store(at: AirtableClient):
    """Fetch from Finary, upsert transactions, run LLM, update Airtable."""
    log.info("Refreshing data from Finary...")
    client = FinaryClient()

    # Fetch balance
    accounts = client.holdings_accounts()
    sci = next((a for a in accounts if a.get("id") == config.SCI_ACCOUNT_ID), None)
    if sci:
        at.set_cash(sci.get("balance", 0) or 0)

    # Fetch all transactions (paginate until empty)
    all_txs = []
    page = 1
    while True:
        batch = client.transactions(config.SCI_ACCOUNT_ID, page=page, per_page=100)
        if not batch:
            break
        all_txs.extend(batch)
        page += 1

    # Normalise
    normalised = []
    for tx in all_txs:
        normalised.append({
            "transaction_id": str(tx.get("id", "")),
            "date":           tx.get("date", "")[:10],   # YYYY-MM-DD
            "amount":         float(tx.get("amount", 0)),
            "label":          tx.get("note") or tx.get("label") or "",
            "category":       "divers",
            "category_status": "pending",
            "confidence":     0.0,
        })

    # Upsert new transactions only
    at.upsert_transactions(normalised)

    # LLM categorization on pending transactions
    existing = at.get_transactions()
    pending  = [t for t in existing if t["category_status"] == "pending"]
    if pending:
        log.info(f"Running LLM on {len(pending)} pending transactions...")
        results = categorize_transactions(pending)
        for r in results:
            at.update_category(r["transaction_id"], r["category"], "pending")

    at.set_last_updated()
    log.info("Refresh complete.")


def _build_dashboard_data(transactions: list[dict]) -> dict:
    """Compute all blocs from the transaction list."""
    confirmed = [t for t in transactions if t["category_status"] == "confirmed"]
    pending   = [t for t in transactions if t["category_status"] == "pending"]

    # ── Loyers ────────────────────────────────────────────────────────────────
    loyer_cards = []
    for loyer_cfg in config.LOYERS:
        montant = loyer_cfg["montant"]
        depuis  = loyer_cfg["depuis"]   # "YYYY-MM"
        appart  = loyer_cfg["appart"]
        caution = loyer_cfg["caution"]

        loyer_txs = [t for t in confirmed
                     if t["category"] == "loyer" and abs(t["amount"] - montant) < 1]

        # Determine tenant name from most recent matching transaction label
        tenant_name = "Inconnu"
        if loyer_txs:
            latest = max(loyer_txs, key=lambda t: t["date"])
            tenant_name = latest["label"].split()[-1].title() if latest["label"] else "Inconnu"

        # Total paid since `depuis`
        total_paid = sum(t["amount"] for t in loyer_txs if t["date"][:7] >= depuis)

        # Paid this month?
        now_ym = datetime.now(timezone.utc).strftime("%Y-%m")
        paid_this_month = any(t["date"][:7] == now_ym for t in loyer_txs)

        loyer_cards.append({
            "appart":         appart,
            "tenant":         tenant_name,
            "montant":        montant,
            "caution":        caution,
            "depuis":         depuis,
            "total_paid":     round(total_paid, 2),
            "paid_this_month": paid_this_month,
        })

    # ── Récurrentes ───────────────────────────────────────────────────────────
    recurrents = [t for t in confirmed if t["category"] == "recurring"]
    prets      = [t for t in confirmed if t["category"] == "pret"]

    # ── Travaux ───────────────────────────────────────────────────────────────
    travaux       = [t for t in confirmed if t["category"] == "travaux"]
    travaux_total = round(sum(abs(t["amount"]) for t in travaux), 2)

    return {
        "loyer_cards":    loyer_cards,
        "recurrents":     recurrents,
        "prets":          prets,
        "travaux":        travaux,
        "travaux_total":  travaux_total,
        "pending":        pending,
        "confidence_threshold": config.LLM_CONFIDENCE_THRESHOLD,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, refresh: bool = False):
    at           = AirtableClient()
    last_updated = at.get_last_updated()

    if refresh or _is_stale(last_updated):
        _fetch_and_store(at)
        last_updated = datetime.now(timezone.utc).replace(tzinfo=None)

    cash         = at.get_cash()
    transactions = at.get_transactions()
    data         = _build_dashboard_data(transactions)

    return templates.TemplateResponse(request, "dashboard.html", {
        "last_updated": last_updated.strftime("%d/%m/%Y %H:%M"),
        "cash":         cash,
        **data,
    })


@app.post("/validate/{transaction_id}")
def validate_transaction(transaction_id: str, payload: ValidatePayload):
    at = AirtableClient()
    at.update_category(transaction_id, payload.category, payload.status)
    return {"ok": True}
