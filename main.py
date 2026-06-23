# main.py
import csv
import io
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

import config
from ingest import run_ingest
from sheets_client import SheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("main")

app       = FastAPI(title="Finance Dashboard")
templates = Jinja2Templates(directory="templates")

# ── APScheduler : refresh quotidien à 06h00 ────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(run_ingest, "cron", hour=6, minute=0, id="daily_ingest")
scheduler.start()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_sheets() -> SheetsClient:
    return SheetsClient(config.GOOGLE_SHEETS_ID, config.GOOGLE_SERVICE_ACCOUNT_JSON)


def _kpis(transactions: list[dict]) -> dict:
    now     = datetime.now()
    curr_ym = now.strftime("%Y-%m")
    prev_ym = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    def spending(ym: str) -> float:
        return abs(sum(float(t.get("amount", 0)) for t in transactions
                       if t.get("date", "")[:7] == ym and float(t.get("amount", 0)) < 0))

    curr  = round(spending(curr_ym), 2)
    prev  = round(spending(prev_ym), 2)
    delta = round((curr - prev) / prev * 100, 1) if prev else 0.0
    return {"current_month": curr, "previous_month": prev, "delta_pct": delta}


def _sorted_desc(txs: list[dict]) -> list[dict]:
    return sorted(txs, key=lambda t: t.get("date", ""), reverse=True)


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    fields = ["date", "label", "amount", "category", "bank", "type"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, profile: str = "commun"):
    if profile not in config.PROFILES:
        profile = "commun"

    sc           = _get_sheets()
    transactions = _sorted_desc(sc.get_transactions(profile=profile))
    last_updated = sc.get_last_updated() or "—"
    kpis         = _kpis(transactions)

    return templates.TemplateResponse(request, "dashboard.html", {
        "profile":      profile,
        "profiles":     {k: v["label"] for k, v in config.PROFILES.items()},
        "transactions": transactions,
        "last_updated": last_updated,
        "kpis":         kpis,
        "now_month":    datetime.now().strftime("%B %Y"),
    })


@app.post("/api/refresh")
def api_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_ingest)
    return {"status": "refresh_started"}


@app.get("/api/transactions.csv")
def export_csv(profile: str = "commun"):
    sc  = _get_sheets()
    txs = _sorted_desc(sc.get_transactions(profile=profile))
    return _csv_response(txs, f"transactions_{profile}.csv")
