# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ── Profils & comptes Finary ───────────────────────────────────────────────────
PROFILES: dict = {
    "jeremy": {
        "label": "Jérémy",
        "accounts": [
            {"id": "69ce0e7d-4d75-4d59-9094-ed8a7bdc3dac", "bank": "CA",     "type": "courant"},
            {"id": "57696d35-caa7-4c01-ad1f-81e53b9e1627", "bank": "CA",     "type": "carte"},
            {"id": "8bcf1c4f-96f4-4749-9912-2e12bd36aecd", "bank": "Bourso", "type": "courant"},
            {"id": "d81f04aa-e9d3-4151-a5af-f91cfd1763dc", "bank": "Bourso", "type": "carte"},
        ],
    },
    "manon": {
        "label": "Manon",
        "accounts": [
            {"id": "8d63155e-5faa-472c-b485-4dd44bb152f6", "bank": "CA",     "type": "courant"},
            {"id": "6090c538-a57c-4f9f-8de2-0530ad24f043", "bank": "CA",     "type": "carte"},
            {"id": "63e50030-33e2-4710-a1a7-297fc0e3715f", "bank": "Bourso", "type": "courant"},
        ],
    },
    "commun": {
        "label": "Commun",
        "accounts": [
            {"id": "47009a48-082c-446e-ba7e-edc95061b3ee", "bank": "Bourso", "type": "courant"},
            {"id": "b2ad95e5-ac50-4b78-a6b1-a4c35e33e3a8", "bank": "CA",     "type": "courant"},
        ],
    },
}

# ── Google Sheets ──────────────────────────────────────────────────────────────
GOOGLE_SHEETS_ID            = "1MBriVcatxhQ_kgJK0DHyF6s7Ly5ZZLD7MO4qqLj22aY"
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

# ── OpenRouter ─────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY       = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL         = "google/gemini-2.5-flash-lite"
LLM_CONFIDENCE_THRESHOLD = 0.7
