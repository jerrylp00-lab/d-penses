# main.py
import csv
import io
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

import config
from ingest import run_ingest
from report import generate_and_send
from sheets_client import SheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("main")

app       = FastAPI(title="Finance Dashboard")
templates = Jinja2Templates(directory="templates")

scheduler = BackgroundScheduler()
scheduler.add_job(run_ingest, "cron", hour=6, minute=0, id="daily_ingest")
scheduler.add_job(generate_and_send, "cron", day_of_week="mon", hour=8, minute=0, id="weekly_report")
scheduler.start()


def _get_sheets() -> SheetsClient:
    return SheetsClient(config.GOOGLE_SHEETS_ID, config.GOOGLE_SERVICE_ACCOUNT_JSON)


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    fields = ["date", "label", "amount", "category", "bank", "type", "profile"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, profile: str = "commun"):
    if profile not in config.PROFILES:
        profile = "commun"

    sc           = _get_sheets()
    transactions = sc.get_transactions(profile=profile)
    last_updated = sc.get_last_updated() or "—"

    return templates.TemplateResponse(request, "dashboard.html", {
        "profile":      profile,
        "profiles":     {k: v["label"] for k, v in config.PROFILES.items()},
        "transactions": transactions,
        "last_updated": last_updated,
    })


@app.post("/api/refresh")
def api_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_ingest)
    return {"status": "refresh_started"}


@app.get("/api/transactions.csv")
def export_csv(profile: str = "commun"):
    sc  = _get_sheets()
    txs = sc.get_transactions(profile=profile)
    return _csv_response(txs, f"transactions_{profile}.csv")


@app.post("/report/send")
def report_send(background_tasks: BackgroundTasks):
    if not config.GMAIL_REFRESH_TOKEN:
        return {"ok": False, "error": "GMAIL_REFRESH_TOKEN non configuré"}
    background_tasks.add_task(generate_and_send, current_week=True)
    return {"ok": True, "sent_to": list(config.REPORT_RECIPIENTS.values())}


@app.get("/report/preview", response_class=HTMLResponse)
def report_preview(profile: str = "jeremy"):
    if profile not in config.REPORT_PROFILES:
        profile = "jeremy"
    results = generate_and_send(dry_run=True)
    if profile not in results:
        return HTMLResponse(content="<p>Erreur : génération du rapport échouée.</p>", status_code=500)
    return HTMLResponse(content=results[profile])
