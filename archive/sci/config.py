# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ── Finary ────────────────────────────────────────────────────────────────────
# Run find_sci_account.py once to get this value
SCI_ACCOUNT_ID = "9416827e-9ee9-4a5e-9eed-bcb097915985"  # COMPTE COURANT S.C.I. SCI 4L — Crédit Agricole

# ── Loyers hardcodés ──────────────────────────────────────────────────────────
LOYERS = [
    {"montant": 640, "appart": "Appart Jean Bart",  "caution": 1200, "type": "appart"},
    {"montant": 690, "appart": "Appart Vallabbé",   "caution": 1300, "type": "appart"},
    {"montant": 60,  "appart": "Garage Vallabbé",   "caution": 0,    "type": "garage"},
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
