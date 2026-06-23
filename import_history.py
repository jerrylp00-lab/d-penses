#!/usr/bin/env python3
"""
import_history.py
─────────────────
Script one-shot : importe tout l'historique Finary dans Google Sheets.
Idempotent — les transactions déjà présentes sont ignorées (déduplication par transaction_id).

Usage:
    python3 import_history.py
"""
import logging
import sys

from ingest import run_ingest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

if __name__ == "__main__":
    try:
        run_ingest()
        print("\n✅ Import historique terminé.")
    except RuntimeError as e:
        if "OTP_REQUIRED" in str(e):
            print("\n📧 OTP envoyé. Relancez : python3 import_history.py")
            sys.exit(0)
        raise
