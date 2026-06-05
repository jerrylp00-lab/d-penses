# find_sci_account.py
"""
Run once to find your SCI account ID.
Copy the ID into config.py → SCI_ACCOUNT_ID
"""
import sys
import logging
from finary_auth import FinaryClient

logging.basicConfig(level=logging.WARNING)

otp = sys.argv[1] if len(sys.argv) > 1 else ""

try:
    client = FinaryClient(otp_code=otp)
except RuntimeError as e:
    if "OTP_REQUIRED" in str(e):
        print("📧 OTP envoyé. Relancez: python find_sci_account.py <CODE>")
        sys.exit(0)
    raise

accounts = client.holdings_accounts()

print(f"\n{'ID':<40} {'Solde':>12}  Nom")
print("-" * 80)
for a in accounts:
    name    = a.get("display_name", "?")
    balance = a.get("balance", 0) or 0
    aid     = a.get("id", "?")
    institution = (a.get("institution") or {}).get("name", "?")
    print(f"{aid:<40} {balance:>10,.0f}€  {name}  [{institution}]")

print("\n👉 Copiez l'ID SCI dans config.py → SCI_ACCOUNT_ID")
