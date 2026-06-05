# SCI Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI-served HTML dashboard showing SCI account transactions, tenant rent status, cash position, LLM-categorized recurring expenses, and a validation UI — all backed by Airtable.

**Architecture:** FastAPI serves a Jinja2 HTML dashboard. On page load, it checks Airtable for a `last_updated` timestamp; if stale (>3 days) or manual refresh requested, it fetches from Finary, stores raw transactions in Airtable, then calls OpenRouter (minimax) to propose categories stored as `pending`. The dashboard renders confirmed transactions in their blocs and pending ones in a "À valider" section with ✓/✗ buttons that POST to FastAPI endpoints updating Airtable.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, pyairtable, python-dotenv, requests, curl_cffi (existing)

---

## File Map

| File | Responsibility |
|------|---------------|
| `config.py` | All hardcoded values (account ID, loyers, caution, dates) |
| `find_sci_account.py` | One-shot script: list Finary accounts → user picks SCI ID |
| `airtable_client.py` | Read/write Airtable (transactions + metadata) |
| `llm_categorizer.py` | Call OpenRouter minimax, return `[{transaction_id, category, confidence}]` |
| `main.py` | FastAPI app: routes, refresh logic, validation endpoints |
| `templates/dashboard.html` | Jinja2 HTML dashboard |
| `requirements.txt` | Dependencies |
| `.env` | Secrets (not versioned) |
| `tests/test_airtable_client.py` | Unit tests for Airtable client |
| `tests/test_llm_categorizer.py` | Unit tests for LLM categorizer |
| `tests/test_main.py` | Integration tests for FastAPI routes |

---

## Task 1: Project setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.111.0
uvicorn==0.29.0
jinja2==3.1.4
python-dotenv==1.0.1
pyairtable==2.3.3
requests==2.32.3
curl_cffi==0.7.3
pytest==8.2.0
httpx==0.27.0
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: no errors.

- [ ] **Step 3: Create .env.example**

```
OPENROUTER_API_KEY=sk-or-...
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=app...
AIRTABLE_TRANSACTIONS_TABLE=Transactions
AIRTABLE_METADATA_TABLE=Metadata
```

- [ ] **Step 4: Create your real .env (never commit this)**

```bash
cp .env.example .env
# Fill in real values
```

- [ ] **Step 5: Create config.py**

```python
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
AIRTABLE_API_KEY          = os.environ["AIRTABLE_API_KEY"]
AIRTABLE_BASE_ID          = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_TRANSACTIONS_TABLE = os.environ.get("AIRTABLE_TRANSACTIONS_TABLE", "Transactions")
AIRTABLE_METADATA_TABLE     = os.environ.get("AIRTABLE_METADATA_TABLE", "Metadata")

# ── OpenRouter ────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL   = "minimax/minimax-01"   # adjust slug if needed
LLM_CONFIDENCE_THRESHOLD = 0.7
```

- [ ] **Step 6: Add .env to .gitignore**

```bash
echo ".env" >> .gitignore
echo "~/.finary_session.json" >> .gitignore
git add .gitignore requirements.txt .env.example config.py
git commit -m "feat: project setup — deps, config, env"
```

---

## Task 2: Airtable — create tables

**Manual step (do in Airtable UI before coding).**

- [ ] **Step 1: Create base in Airtable (or use existing)**

Note the Base ID from the URL: `https://airtable.com/appXXXXXXXXX/...` → `appXXXXXXXXX`

- [ ] **Step 2: Create table `Transactions` with these fields**

| Field name | Field type |
|-----------|-----------|
| `transaction_id` | Single line text |
| `date` | Date |
| `amount` | Number (allow negative) |
| `label` | Single line text |
| `category` | Single line text |
| `category_status` | Single select: `pending`, `confirmed`, `rejected` |
| `confidence` | Number (decimal) |

- [ ] **Step 3: Create table `Metadata` with these fields**

| Field name | Field type |
|-----------|-----------|
| `key` | Single line text |
| `value` | Single line text |

- [ ] **Step 4: Add initial metadata row**

In Airtable UI, add one row to `Metadata`:
- `key`: `last_updated`
- `value`: `2000-01-01T00:00:00` (forces first refresh)

- [ ] **Step 5: Copy your Base ID and API key into .env**

```
AIRTABLE_API_KEY=pat...
AIRTABLE_BASE_ID=appXXXXXXXX
```

---

## Task 3: find_sci_account.py (one-shot setup)

**Files:**
- Create: `find_sci_account.py`

- [ ] **Step 1: Create find_sci_account.py**

```python
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
```

- [ ] **Step 2: Run it**

```bash
python find_sci_account.py
```

Expected: table of accounts with IDs and balances. Find the Crédit Agricole SCI (~3000€).

- [ ] **Step 3: Copy the ID into config.py**

Edit `config.py`:
```python
SCI_ACCOUNT_ID = "the-real-id-you-just-found"
```

- [ ] **Step 4: Commit**

```bash
git add find_sci_account.py config.py
git commit -m "feat: add find_sci_account script, set SCI_ACCOUNT_ID"
```

---

## Task 4: airtable_client.py

**Files:**
- Create: `airtable_client.py`
- Create: `tests/test_airtable_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_airtable_client.py
from unittest.mock import MagicMock, patch
import pytest
from airtable_client import AirtableClient


@pytest.fixture
def client():
    with patch("airtable_client.Api") as MockApi:
        mock_api = MagicMock()
        MockApi.return_value = mock_api
        c = AirtableClient.__new__(AirtableClient)
        c._transactions = MagicMock()
        c._metadata     = MagicMock()
        yield c


def test_get_last_updated_returns_datetime(client):
    from datetime import datetime
    client._metadata.all.return_value = [
        {"fields": {"key": "last_updated", "value": "2026-01-01T12:00:00"}}
    ]
    result = client.get_last_updated()
    assert isinstance(result, datetime)
    assert result.year == 2026


def test_get_last_updated_missing_returns_epoch(client):
    from datetime import datetime
    client._metadata.all.return_value = []
    result = client.get_last_updated()
    assert result == datetime(2000, 1, 1)


def test_upsert_transactions_calls_create(client):
    txs = [{"transaction_id": "t1", "date": "2026-06-01",
             "amount": 690.0, "label": "LOYER DUPONT"}]
    client._transactions.all.return_value = []  # no existing
    client.upsert_transactions(txs)
    client._transactions.create.assert_called_once()


def test_get_transactions_returns_list(client):
    client._transactions.all.return_value = [
        {"id": "rec1", "fields": {
            "transaction_id": "t1", "date": "2026-06-01",
            "amount": 690.0, "label": "LOYER", "category": "loyer",
            "category_status": "confirmed", "confidence": 0.95
        }}
    ]
    result = client.get_transactions()
    assert len(result) == 1
    assert result[0]["transaction_id"] == "t1"


def test_update_category_status(client):
    client._transactions.all.return_value = [
        {"id": "rec1", "fields": {"transaction_id": "t1"}}
    ]
    client.update_category("t1", category="loyer", status="confirmed")
    client._transactions.update.assert_called_once_with(
        "rec1", {"category": "loyer", "category_status": "confirmed"}
    )
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_airtable_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'airtable_client'`

- [ ] **Step 3: Implement airtable_client.py**

```python
# airtable_client.py
from datetime import datetime
from typing import Optional
from pyairtable import Api
import config


class AirtableClient:
    def __init__(self):
        api = Api(config.AIRTABLE_API_KEY)
        base = api.base(config.AIRTABLE_BASE_ID)
        self._transactions = base.table(config.AIRTABLE_TRANSACTIONS_TABLE)
        self._metadata     = base.table(config.AIRTABLE_METADATA_TABLE)

    # ── Metadata ───────────────────────────────────────────────────────────────

    def get_last_updated(self) -> datetime:
        rows = self._metadata.all(formula="{key}='last_updated'")
        if not rows:
            return datetime(2000, 1, 1)
        value = rows[0]["fields"].get("value", "2000-01-01T00:00:00")
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime(2000, 1, 1)

    def set_last_updated(self, dt: Optional[datetime] = None):
        dt = dt or datetime.utcnow()
        value = dt.isoformat()
        rows = self._metadata.all(formula="{key}='last_updated'")
        if rows:
            self._metadata.update(rows[0]["id"], {"value": value})
        else:
            self._metadata.create({"key": "last_updated", "value": value})

    def set_cash(self, amount: float):
        rows = self._metadata.all(formula="{key}='cash'")
        value = str(round(amount, 2))
        if rows:
            self._metadata.update(rows[0]["id"], {"value": value})
        else:
            self._metadata.create({"key": "cash", "value": value})

    def get_cash(self) -> Optional[float]:
        rows = self._metadata.all(formula="{key}='cash'")
        if not rows:
            return None
        try:
            return float(rows[0]["fields"]["value"])
        except (KeyError, ValueError):
            return None

    # ── Transactions ───────────────────────────────────────────────────────────

    def get_transactions(self) -> list[dict]:
        rows = self._transactions.all(sort=["date"])
        result = []
        for r in rows:
            f = r["fields"]
            result.append({
                "record_id":       r["id"],
                "transaction_id":  f.get("transaction_id", ""),
                "date":            f.get("date", ""),
                "amount":          float(f.get("amount", 0)),
                "label":           f.get("label", ""),
                "category":        f.get("category", "divers"),
                "category_status": f.get("category_status", "pending"),
                "confidence":      float(f.get("confidence", 0)),
            })
        return result

    def upsert_transactions(self, transactions: list[dict]):
        """Insert new transactions; skip existing (by transaction_id)."""
        existing_ids = {
            r["fields"].get("transaction_id")
            for r in self._transactions.all(fields=["transaction_id"])
        }
        new = [t for t in transactions if t["transaction_id"] not in existing_ids]
        for tx in new:
            self._transactions.create({
                "transaction_id":  tx["transaction_id"],
                "date":            tx["date"],
                "amount":          tx["amount"],
                "label":           tx["label"],
                "category":        tx.get("category", "divers"),
                "category_status": tx.get("category_status", "pending"),
                "confidence":      tx.get("confidence", 0.0),
            })

    def update_category(self, transaction_id: str, category: str, status: str):
        rows = self._transactions.all(
            formula=f"{{transaction_id}}='{transaction_id}'"
        )
        if not rows:
            raise ValueError(f"Transaction {transaction_id} not found")
        self._transactions.update(rows[0]["id"], {
            "category":        category,
            "category_status": status,
        })
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_airtable_client.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add airtable_client.py tests/test_airtable_client.py
git commit -m "feat: Airtable client with upsert, metadata, category update"
```

---

## Task 5: llm_categorizer.py

**Files:**
- Create: `llm_categorizer.py`
- Create: `tests/test_llm_categorizer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_categorizer.py
from unittest.mock import patch, MagicMock
import json
import pytest
from llm_categorizer import categorize_transactions, _build_prompt, _parse_response


def test_build_prompt_contains_transactions():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -112.0, "label": "ASSURANCE HABITATION"}]
    prompt = _build_prompt(txs)
    assert "t1" in prompt
    assert "ASSURANCE HABITATION" in prompt


def test_parse_response_valid():
    raw = json.dumps([
        {"transaction_id": "t1", "category": "recurring", "confidence": 0.9}
    ])
    result = _parse_response(raw)
    assert result == [{"transaction_id": "t1", "category": "recurring", "confidence": 0.9}]


def test_parse_response_invalid_returns_empty():
    result = _parse_response("not json at all")
    assert result == []


def test_categorize_transactions_calls_api():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -112.0, "label": "ASSURANCE"}]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": json.dumps([
            {"transaction_id": "t1", "category": "recurring", "confidence": 0.9}
        ])}}]
    }
    with patch("llm_categorizer.requests.post", return_value=mock_response):
        result = categorize_transactions(txs)
    assert len(result) == 1
    assert result[0]["category"] == "recurring"


def test_categorize_transactions_api_fail_returns_divers():
    txs = [{"transaction_id": "t1", "date": "2026-06-01", "amount": -50.0, "label": "MISC"}]
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server error"
    with patch("llm_categorizer.requests.post", return_value=mock_response):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "divers"
    assert result[0]["confidence"] == 0.0
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_llm_categorizer.py -v
```

Expected: `ModuleNotFoundError: No module named 'llm_categorizer'`

- [ ] **Step 3: Implement llm_categorizer.py**

```python
# llm_categorizer.py
import json
import logging
import requests
import config

log = logging.getLogger("llm_categorizer")

CATEGORIES = ["loyer", "pret", "recurring", "travaux", "divers"]

SYSTEM_PROMPT = """Tu es un assistant comptable pour une SCI immobilière française.
Classe chaque transaction bancaire dans exactement une de ces catégories :
- loyer       : virement entrant de 690€ ou 640€ (loyer locataire)
- pret        : remboursement de prêt bancaire sortant et régulier
- recurring   : dépense sortante récurrente (même libellé et montant approximatif chaque mois)
- travaux     : paiement par chèque OU libellé contenant travaux/artisan/matériaux/rénovation
- divers      : tout ce qui ne rentre pas dans les catégories ci-dessus

Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour.
Format : [{"transaction_id": "...", "category": "...", "confidence": 0.0}]
confidence entre 0.0 et 1.0."""


def _build_prompt(transactions: list[dict]) -> str:
    lines = [f"- id={t['transaction_id']} date={t['date']} montant={t['amount']}€ libellé={t['label']}"
             for t in transactions]
    return "Transactions à classifier :\n" + "\n".join(lines)


def _parse_response(raw: str) -> list[dict]:
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    """
    Send transactions to OpenRouter LLM for categorization.
    Returns list of {transaction_id, category, confidence}.
    On any failure, returns divers with confidence 0 for all transactions.
    """
    if not transactions:
        return []

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sci-dashboard.local",
        "X-Title": "SCI Dashboard",
    }
    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(transactions)},
        ],
        "temperature": 0.1,
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        log.error(f"LLM request failed: {e}")
        return _fallback(transactions)

    if resp.status_code != 200:
        log.error(f"LLM error {resp.status_code}: {resp.text[:200]}")
        return _fallback(transactions)

    raw = resp.json()["choices"][0]["message"]["content"]
    parsed = _parse_response(raw)

    if not parsed:
        log.warning("LLM returned unparseable response, falling back to divers")
        return _fallback(transactions)

    # Ensure all transactions have a result; fill missing with divers
    result_map = {r["transaction_id"]: r for r in parsed}
    return [
        result_map.get(t["transaction_id"], {
            "transaction_id": t["transaction_id"],
            "category": "divers",
            "confidence": 0.0,
        })
        for t in transactions
    ]


def _fallback(transactions: list[dict]) -> list[dict]:
    return [
        {"transaction_id": t["transaction_id"], "category": "divers", "confidence": 0.0}
        for t in transactions
    ]
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_llm_categorizer.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add llm_categorizer.py tests/test_llm_categorizer.py
git commit -m "feat: LLM categorizer with OpenRouter + fallback"
```

---

## Task 6: main.py — FastAPI app + refresh logic

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_main.py
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def mock_deps():
    """Patch Airtable and Finary so tests don't hit real APIs."""
    with patch("main.AirtableClient") as MockAirtable, \
         patch("main.FinaryClient") as MockFinary:

        mock_at = MagicMock()
        MockAirtable.return_value = mock_at
        mock_at.get_last_updated.return_value = __import__("datetime").datetime(2026, 6, 6)
        mock_at.get_cash.return_value = 3100.0
        mock_at.get_transactions.return_value = [
            {"record_id": "rec1", "transaction_id": "t1", "date": "2026-06-01",
             "amount": 690.0, "label": "LOYER DUPONT", "category": "loyer",
             "category_status": "confirmed", "confidence": 0.95},
            {"record_id": "rec2", "transaction_id": "t2", "date": "2026-06-01",
             "amount": -112.0, "label": "ASSURANCE HABITATION", "category": "recurring",
             "category_status": "pending", "confidence": 0.85},
        ]

        mock_finary = MagicMock()
        MockFinary.return_value = mock_finary

        yield mock_at, mock_finary


@pytest.fixture
def client(mock_deps):
    from main import app
    return TestClient(app)


def test_dashboard_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SCI" in resp.text


def test_confirm_category(client, mock_deps):
    mock_at, _ = mock_deps
    resp = client.post("/validate/t1", json={"category": "loyer", "status": "confirmed"})
    assert resp.status_code == 200
    mock_at.update_category.assert_called_once_with("t1", "loyer", "confirmed")


def test_reject_category(client, mock_deps):
    mock_at, _ = mock_deps
    resp = client.post("/validate/t2", json={"category": "divers", "status": "rejected"})
    assert resp.status_code == 200
    mock_at.update_category.assert_called_once_with("t2", "divers", "rejected")
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Implement main.py**

```python
# main.py
import logging
from datetime import datetime, timedelta
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
    return (datetime.utcnow() - last_updated) > timedelta(days=config.CACHE_TTL_DAYS)


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

    # LLM categorization on all transactions (re-categorise pending)
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
        now_ym = datetime.utcnow().strftime("%Y-%m")
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
        last_updated = datetime.utcnow()

    cash         = at.get_cash()
    transactions = at.get_transactions()
    data         = _build_dashboard_data(transactions)

    return templates.TemplateResponse("dashboard.html", {
        "request":      request,
        "last_updated": last_updated.strftime("%d/%m/%Y %H:%M"),
        "cash":         cash,
        **data,
    })


@app.post("/validate/{transaction_id}")
def validate_transaction(transaction_id: str, payload: ValidatePayload):
    at = AirtableClient()
    at.update_category(transaction_id, payload.category, payload.status)
    return {"ok": True}
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_main.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: FastAPI app with dashboard route, refresh logic, validation endpoint"
```

---

## Task 7: dashboard.html template

**Files:**
- Create: `templates/dashboard.html`

- [ ] **Step 1: Create templates/ directory**

```bash
mkdir -p templates
```

- [ ] **Step 2: Create templates/dashboard.html**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SCI Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #111; padding: 24px; }
    h1 { font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; }
    h2 { font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: #444; text-transform: uppercase; letter-spacing: .05em; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
    .meta   { font-size: .85rem; color: #666; }
    .refresh-btn { padding: 6px 14px; background: #111; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: .85rem; }
    .refresh-btn:hover { background: #333; }
    .grid   { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 32px; }
    .card   { background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
    .badge  { display: inline-block; padding: 3px 10px; border-radius: 99px; font-size: .75rem; font-weight: 600; }
    .badge-ok  { background: #dcfce7; color: #166534; }
    .badge-late { background: #fee2e2; color: #991b1b; }
    .badge-warn { background: #fef9c3; color: #854d0e; }
    .amount { font-size: 1.3rem; font-weight: 700; }
    .sub    { font-size: .82rem; color: #666; margin-top: 4px; }
    .section { margin-bottom: 32px; }
    table   { width: 100%; border-collapse: collapse; font-size: .88rem; }
    th      { text-align: left; padding: 8px 12px; border-bottom: 2px solid #e5e7eb; color: #444; font-weight: 600; }
    td      { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
    tr:last-child td { border-bottom: none; }
    .pending-row { opacity: .45; font-style: italic; }
    .pending-row:hover { opacity: .7; }
    .cat-label { font-size: .78rem; background: #f3f4f6; border-radius: 4px; padding: 2px 6px; }
    .btn-sm { padding: 3px 10px; border-radius: 5px; border: 1px solid #d1d5db; cursor: pointer; font-size: .8rem; }
    .btn-confirm { background: #dcfce7; color: #166534; }
    .btn-reject  { background: #fee2e2; color: #991b1b; }
    select.cat-select { font-size: .8rem; padding: 2px 6px; border-radius: 5px; border: 1px solid #d1d5db; }
    .cash-amount { font-size: 2rem; font-weight: 800; }
  </style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div>
    <h1>SCI Dashboard</h1>
    <p class="meta">Dernière mise à jour : {{ last_updated }}</p>
  </div>
  <button class="refresh-btn" onclick="location.href='/?refresh=true'">⟳ Rafraîchir</button>
</div>

<!-- Bloc 1: Cash -->
<div class="section">
  <h2>💰 Cash disponible</h2>
  <div class="card" style="display:inline-block; min-width:200px;">
    <div class="cash-amount">{{ "%.2f"|format(cash or 0) }} €</div>
    <div class="sub">Solde compte SCI Crédit Agricole</div>
  </div>
</div>

<!-- Bloc 2: Loyers -->
<div class="section">
  <h2>🏠 Loyers</h2>
  <div class="grid">
    {% for card in loyer_cards %}
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">
        <div>
          <div style="font-weight:700;font-size:1.05rem;">{{ card.appart }}</div>
          <div class="sub">{{ card.tenant }}</div>
        </div>
        {% if card.paid_this_month %}
        <span class="badge badge-ok">À jour</span>
        {% else %}
        <span class="badge badge-late">En retard</span>
        {% endif %}
      </div>
      <div class="amount">{{ card.montant }} €<span style="font-size:.9rem;font-weight:400;color:#666;">/mois</span></div>
      <div class="sub" style="margin-top:8px;">Depuis {{ card.depuis }} · Total payé : <strong>{{ "%.0f"|format(card.total_paid) }} €</strong></div>
      <div class="sub">Caution : {{ card.caution }} €</div>
    </div>
    {% endfor %}
  </div>
</div>

<!-- Bloc 3: Récurrentes + Prêts -->
<div class="section">
  <h2>🔁 Dépenses récurrentes</h2>
  {% if recurrents %}
  <div class="card" style="margin-bottom:16px;">
    <table>
      <thead><tr><th>Date</th><th>Libellé</th><th>Montant</th></tr></thead>
      <tbody>
        {% for t in recurrents %}
        <tr>
          <td>{{ t.date }}</td>
          <td>{{ t.label }}</td>
          <td style="color:#dc2626;">{{ "%.2f"|format(t.amount) }} €</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <p class="sub">Aucune dépense récurrente confirmée.</p>
  {% endif %}

  {% if prets %}
  <h2 style="margin-top:16px;">🏦 Prêts bancaires</h2>
  <div class="card">
    <table>
      <thead><tr><th>Date</th><th>Libellé</th><th>Montant</th></tr></thead>
      <tbody>
        {% for t in prets %}
        <tr>
          <td>{{ t.date }}</td>
          <td>{{ t.label }}</td>
          <td style="color:#dc2626;">{{ "%.2f"|format(t.amount) }} €</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
</div>

<!-- Bloc 4: Travaux -->
<div class="section">
  <h2>🔨 Travaux</h2>
  {% if travaux %}
  <div class="card">
    <div style="font-size:1.1rem;font-weight:700;margin-bottom:12px;">Total : {{ "%.2f"|format(travaux_total) }} €</div>
    <table>
      <thead><tr><th>Date</th><th>Libellé</th><th>Montant</th></tr></thead>
      <tbody>
        {% for t in travaux %}
        <tr>
          <td>{{ t.date }}</td>
          <td>{{ t.label }}</td>
          <td style="color:#dc2626;">{{ "%.2f"|format(t.amount) }} €</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <p class="sub">Aucun travaux confirmés.</p>
  {% endif %}
</div>

<!-- Bloc 5: À valider -->
{% if pending %}
<div class="section">
  <h2>⚠️ À valider ({{ pending|length }})</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Date</th><th>Libellé</th><th>Montant</th>
          <th>Catégorie proposée</th><th>Confiance</th><th>Action</th>
        </tr>
      </thead>
      <tbody>
        {% for t in pending %}
        <tr class="pending-row" id="row-{{ t.transaction_id }}">
          <td>{{ t.date }}</td>
          <td>{{ t.label }}</td>
          <td>{{ "%.2f"|format(t.amount) }} €</td>
          <td>
            <select class="cat-select" id="cat-{{ t.transaction_id }}">
              {% for cat in ["loyer","pret","recurring","travaux","divers"] %}
              <option value="{{ cat }}" {% if cat == t.category %}selected{% endif %}>{{ cat }}</option>
              {% endfor %}
            </select>
          </td>
          <td>
            {% if t.confidence < confidence_threshold %}
            <span class="badge badge-warn">{{ "%.0f"|format(t.confidence * 100) }}%</span>
            {% else %}
            {{ "%.0f"|format(t.confidence * 100) }}%
            {% endif %}
          </td>
          <td style="display:flex;gap:6px;">
            <button class="btn-sm btn-confirm" onclick="validate('{{ t.transaction_id }}','confirmed')">✓</button>
            <button class="btn-sm btn-reject"  onclick="validate('{{ t.transaction_id }}','rejected')">✗</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endif %}

<script>
async function validate(txId, status) {
  const select   = document.getElementById('cat-' + txId);
  const category = select ? select.value : 'divers';
  const resp = await fetch('/validate/' + txId, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({category, status}),
  });
  if (resp.ok) {
    const row = document.getElementById('row-' + txId);
    if (row) row.remove();
  }
}
</script>

</body>
</html>
```

- [ ] **Step 3: Start the app and visually verify**

```bash
uvicorn main:app --reload --port 8000
```

Open: http://localhost:8000

Expected: dashboard loads with all 4 blocs + "À valider" section.

- [ ] **Step 4: Commit**

```bash
git add templates/dashboard.html
git commit -m "feat: HTML dashboard template with all blocs and validation UI"
```

---

## Task 8: Run all tests + final smoke test

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Run the app end-to-end**

```bash
uvicorn main:app --reload --port 8000
```

Visit http://localhost:8000?refresh=true — data fetched, LLM runs, dashboard populates.

- [ ] **Step 3: Test validation UI**

In the "À valider" section: click ✓ on a transaction. Row disappears. Reload page — transaction now appears in the correct confirmed bloc.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: SCI dashboard complete — Finary + Airtable + LLM categorization"
```
