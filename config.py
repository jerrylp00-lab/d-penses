# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ── Finary ────────────────────────────────────────────────────────────────────
# Run find_sci_account.py once to get this value
SCI_ACCOUNT_ID = "9416827e-9ee9-4a5e-9eed-bcb097915985"  # COMPTE COURANT S.C.I. SCI 4L — Crédit Agricole

# ── Loyers hardcodés ──────────────────────────────────────────────────────────
LOYERS = [
    {
        "appart": "Appart 1",
        "montant": 690,
        "caution": 1380,
        "depuis": "2025-09",   # YYYY-MM
    },
    {
        "appart": "Appart 2",
        "montant": 640,
        "caution": 1280,
        "depuis": "2025-09",
    },
]

# ── Cache ─────────────────────────────────────────────────────────────────────
CACHE_TTL_DAYS = 3

# ── Airtable ──────────────────────────────────────────────────────────────────
AIRTABLE_API_KEY            = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_BASE_ID            = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_TRANSACTIONS_TABLE = os.environ.get("AIRTABLE_TRANSACTIONS_TABLE", "Transactions")
AIRTABLE_METADATA_TABLE     = os.environ.get("AIRTABLE_METADATA_TABLE", "Metadata")

# ── OpenRouter ────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL   = "google/gemini-2.5-flash-lite"
LLM_CONFIDENCE_THRESHOLD = 0.7
