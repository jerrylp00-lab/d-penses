# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ── Finary ────────────────────────────────────────────────────────────────────
# Run find_sci_account.py once to get this value
SCI_ACCOUNT_ID = "REPLACE_ME"

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
OPENROUTER_MODEL   = "minimax/minimax-01"   # adjust slug if needed
LLM_CONFIDENCE_THRESHOLD = 0.7
