# main.py
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from airtable_client import AirtableClient
from finary_auth import FinaryClient
from llm_categorizer import categorize_transactions
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("main")

app       = FastAPI(title="SCI Dashboard")
templates = Jinja2Templates(directory="templates")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_stale(last_updated: datetime) -> bool:
    return (datetime.now(timezone.utc).replace(tzinfo=None) - last_updated) > timedelta(days=config.CACHE_TTL_DAYS)


def _fetch_and_store(at: AirtableClient):
    log.info("Refreshing data from Finary...")
    client = FinaryClient()

    accounts = client.holdings_accounts()
    sci = next((a for a in accounts if a.get("id") == config.SCI_ACCOUNT_ID), None)
    if sci:
        at.set_cash(sci.get("balance", 0) or 0)

    all_txs = []
    page = 1
    while True:
        batch = client.transactions(config.SCI_ACCOUNT_ID, page=page, per_page=100)
        if not batch:
            break
        all_txs.extend(batch)
        page += 1

    normalised = [
        {
            "transaction_id":  str(tx.get("id", "")),
            "date":            (tx.get("display_date") or tx.get("date", ""))[:10],
            "amount":          float(tx.get("value", 0)),
            "label":           tx.get("display_name") or tx.get("name") or "",
            "category":        "divers",
            "category_status": "confirmed",
            "confidence":      0.0,
        }
        for tx in all_txs
    ]

    at.upsert_transactions(normalised)

    existing = at.get_transactions()
    if existing:
        log.info(f"Running LLM on {len(existing)} transactions...")
        results = categorize_transactions(existing)
        for r in results:
            at.update_category(r["transaction_id"], r["category"], "confirmed")

    at.set_last_updated()
    log.info("Refresh complete.")


def _sorted_desc(txs: list[dict]) -> list[dict]:
    return sorted(txs, key=lambda t: t["date"], reverse=True)


def _build_dashboard_data(transactions: list[dict]) -> dict:
    now_ym = datetime.now().strftime("%Y-%m")

    recettes_mois = sum(t["amount"] for t in transactions if t["amount"] > 0 and t["date"][:7] == now_ym)
    depenses_mois = abs(sum(t["amount"] for t in transactions if t["amount"] < 0 and t["date"][:7] == now_ym))

    loyer_cards = []
    for loyer_cfg in config.LOYERS:
        montant = loyer_cfg["montant"]
        matching = _sorted_desc([
            t for t in transactions
            if t["category"] == "loyer" and abs(t["amount"] - montant) < 1
        ])
        last_tx = {"date": matching[0]["date"], "amount": matching[0]["amount"]} if matching else None
        loyer_cards.append({
            "appart":          loyer_cfg["appart"],
            "type":            loyer_cfg["type"],
            "montant_attendu": montant,
            "last_tx":         last_tx,
            "all_txs":         matching,
        })

    def _bloc(category: str) -> tuple[list[dict], list[dict]]:
        all_txs = _sorted_desc([t for t in transactions if t["category"] == category])
        return all_txs[:5], all_txs

    pr_last5, pr_all = _bloc("pret_recurrent")
    pe_last5, pe_all = _bloc("pret_exceptionnel")
    tr_last5, tr_all = _bloc("travaux")
    re_last5, re_all = _bloc("recurring")

    all_sorted = _sorted_desc(transactions)

    return {
        "recettes_mois":           round(recettes_mois, 2),
        "depenses_mois":           round(depenses_mois, 2),
        "loyer_cards":             loyer_cards,
        "pret_recurrent_last5":    pr_last5,
        "pret_recurrent_all":      pr_all,
        "pret_exceptionnel_last5": pe_last5,
        "pret_exceptionnel_all":   pe_all,
        "travaux_total":           round(sum(abs(t["amount"]) for t in tr_all), 2),
        "travaux_last5":           tr_last5,
        "travaux_all":             tr_all,
        "recurrents_last5":        re_last5,
        "recurrents_all":          re_all,
        "recent_last5":            all_sorted[:5],
        "recent_all":              all_sorted,
    }


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        content = "date,label,amount,category\r\n"
    else:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["date", "label", "amount", "category"],
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        content = output.getvalue()
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, refresh: bool = False):
    refresh_error: Optional[str] = None
    at           = AirtableClient()
    last_updated = at.get_last_updated()

    if refresh or _is_stale(last_updated):
        try:
            _fetch_and_store(at)
            last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
        except Exception as e:
            log.error(f"Refresh failed: {e}", exc_info=True)
            refresh_error = str(e)

    cash         = at.get_cash()
    transactions = at.get_transactions()
    data         = _build_dashboard_data(transactions)

    return templates.TemplateResponse(request, "dashboard.html", {
        "last_updated":  last_updated.strftime("%d/%m/%Y %H:%M"),
        "cash":          cash,
        "refresh_error": refresh_error,
        **data,
    })


@app.get("/export/loyers.csv")
def export_loyers():
    at = AirtableClient()
    txs = [t for t in at.get_transactions() if t["category"] == "loyer"]
    return _csv_response(_sorted_desc(txs), "loyers.csv")


@app.get("/export/pret_recurrent.csv")
def export_pret_recurrent():
    at = AirtableClient()
    txs = [t for t in at.get_transactions() if t["category"] == "pret_recurrent"]
    return _csv_response(_sorted_desc(txs), "pret_recurrent.csv")


@app.get("/export/pret_exceptionnel.csv")
def export_pret_exceptionnel():
    at = AirtableClient()
    txs = [t for t in at.get_transactions() if t["category"] == "pret_exceptionnel"]
    return _csv_response(_sorted_desc(txs), "pret_exceptionnel.csv")


@app.get("/export/travaux.csv")
def export_travaux():
    at = AirtableClient()
    txs = [t for t in at.get_transactions() if t["category"] == "travaux"]
    return _csv_response(_sorted_desc(txs), "travaux.csv")


@app.get("/export/recurrents.csv")
def export_recurrents():
    at = AirtableClient()
    txs = [t for t in at.get_transactions() if t["category"] == "recurring"]
    return _csv_response(_sorted_desc(txs), "recurrents.csv")


@app.get("/export/transactions.csv")
def export_transactions():
    at = AirtableClient()
    txs = at.get_transactions()
    return _csv_response(_sorted_desc(txs), "transactions.csv")
