# Personal Finance Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le dashboard SCI par un dashboard de dépenses personnelles multi-profils (Jérémy, Manon, Commun) alimenté par Finary et stocké dans Google Sheets.

**Architecture:** Approche A — SCI archivé dans `archive/sci/`, app reconstruite propre. FastAPI + Jinja2 + FinaryClient existant + gspread pour Google Sheets. L'ingest est idempotent (déduplication par `transaction_id`) et peut être déclenché manuellement ou quotidiennement via APScheduler.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, gspread, google-auth, apscheduler, FinaryClient (existant), OpenRouter LLM (existant)

---

## File Map

| Fichier | Action | Responsabilité |
|---|---|---|
| `archive/sci/` | Créer | Copie de sauvegarde de l'existant |
| `config.py` | Réécrire | PROFILES, IDs comptes, Sheets config |
| `sheets_client.py` | Créer | Wrapper gspread (read/write transactions + metadata) |
| `llm_categorizer.py` | Modifier | Nouveau prompt finance perso, nouvelles catégories |
| `ingest.py` | Créer | Logique d'ingest : fetch Finary → filtre → déduplique → catégorise → Sheets |
| `import_history.py` | Créer | Script one-shot : appelle `run_ingest()` sans filtre de date |
| `main.py` | Réécrire | Routes FastAPI + APScheduler quotidien |
| `templates/dashboard.html` | Réécrire | Onglets profil, KPIs, liste transactions, bouton refresh |
| `requirements.txt` | Modifier | Remplacer pyairtable par gspread + google-auth + apscheduler |
| `tests/test_config.py` | Créer | Validation structure PROFILES |
| `tests/test_sheets_client.py` | Créer | Tests SheetsClient avec gspread mocké |
| `tests/test_ingest.py` | Créer | Tests normalisation, filtre différé, déduplication |

---

## Task 1: Archive SCI & mise à jour des dépendances

**Files:**
- Create: `archive/sci/` (répertoire)
- Modify: `requirements.txt`

- [ ] **Step 1: Archiver les fichiers SCI existants**

```bash
mkdir -p archive/sci/templates
cp main.py archive/sci/main.py
cp config.py archive/sci/config.py
cp airtable_client.py archive/sci/airtable_client.py
cp templates/dashboard.html archive/sci/templates/dashboard.html
```

- [ ] **Step 2: Mettre à jour requirements.txt**

Remplacer le contenu de `requirements.txt` par :

```
fastapi==0.111.0
uvicorn==0.29.0
jinja2==3.1.4
python-dotenv==1.0.1
requests==2.32.3
curl_cffi==0.7.3
gspread==6.1.2
google-auth==2.29.0
apscheduler==3.10.4
pytest==8.2.0
httpx==0.27.0
```

- [ ] **Step 3: Installer les nouvelles dépendances**

```bash
pip install gspread==6.1.2 google-auth==2.29.0 apscheduler==3.10.4
```

Expected: installation sans erreur

- [ ] **Step 4: Commit**

```bash
git add archive/ requirements.txt
git commit -m "chore: archive SCI dashboard, add gspread+apscheduler deps"
```

---

## Task 2: Nouveau config.py

**Files:**
- Rewrite: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Écrire le test de validation PROFILES**

Créer `tests/test_config.py` :

```python
import config

REQUIRED_ACCOUNT_KEYS = {"id", "bank", "type"}
VALID_BANKS = {"CA", "Bourso"}
VALID_TYPES = {"courant", "carte"}
VALID_PROFILES = {"jeremy", "manon", "commun"}


def test_profiles_keys():
    assert set(config.PROFILES.keys()) == VALID_PROFILES


def test_each_profile_has_label_and_accounts():
    for name, profile in config.PROFILES.items():
        assert "label" in profile, f"{name} missing 'label'"
        assert "accounts" in profile, f"{name} missing 'accounts'"
        assert len(profile["accounts"]) > 0, f"{name} has no accounts"


def test_account_structure():
    for name, profile in config.PROFILES.items():
        for acc in profile["accounts"]:
            missing = REQUIRED_ACCOUNT_KEYS - acc.keys()
            assert not missing, f"{name}: account missing keys {missing}"
            assert acc["bank"] in VALID_BANKS, f"{name}: unknown bank {acc['bank']}"
            assert acc["type"] in VALID_TYPES, f"{name}: unknown type {acc['type']}"


def test_no_duplicate_account_ids_across_profiles():
    seen = {}
    for name, profile in config.PROFILES.items():
        for acc in profile["accounts"]:
            aid = acc["id"]
            assert aid not in seen, (
                f"Account {aid} appears in both '{seen[aid]}' and '{name}'"
            )
            seen[aid] = name


def test_sheets_config_present():
    assert config.GOOGLE_SHEETS_ID
    assert config.GOOGLE_SERVICE_ACCOUNT_JSON
    assert config.OPENROUTER_API_KEY
    assert config.OPENROUTER_MODEL
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — `module 'config' has no attribute 'PROFILES'`

- [ ] **Step 3: Écrire le nouveau config.py**

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ── Profils & comptes Finary ───────────────────────────────────────────────────
PROFILES: dict = {
    "jeremy": {
        "label": "Jérémy",
        "accounts": [
            {"id": "69ce0e7d-4d75-4d59-9094-ed8a7bdc3dac", "bank": "CA",    "type": "courant"},
            {"id": "57696d35-caa7-4c01-ad1f-81e53b9e1627", "bank": "CA",    "type": "carte"},
            {"id": "8bcf1c4f-96f4-4749-9912-2e12bd36aecd", "bank": "Bourso", "type": "courant"},
            {"id": "d81f04aa-e9d3-4151-a5af-f91cfd1763dc", "bank": "Bourso", "type": "carte"},
        ],
    },
    "manon": {
        "label": "Manon",
        "accounts": [
            {"id": "8d63155e-5faa-472c-b485-4dd44bb152f6", "bank": "CA",    "type": "courant"},
            {"id": "6090c538-a57c-4f9f-8de2-0530ad24f043", "bank": "CA",    "type": "carte"},
            {"id": "63e50030-33e2-4710-a1a7-297fc0e3715f", "bank": "Bourso", "type": "courant"},
        ],
    },
    "commun": {
        "label": "Commun",
        "accounts": [
            {"id": "47009a48-082c-446e-ba7e-edc95061b3ee", "bank": "Bourso", "type": "courant"},
            {"id": "b2ad95e5-ac50-4b78-a6b1-a4c35e33e3a8", "bank": "CA",    "type": "courant"},
        ],
    },
}

# ── Google Sheets ──────────────────────────────────────────────────────────────
GOOGLE_SHEETS_ID             = "1MBriVcatxhQ_kgJK0DHyF6s7Ly5ZZLD7MO4qqLj22aY"
GOOGLE_SERVICE_ACCOUNT_JSON  = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]  # chemin vers le fichier JSON

# ── OpenRouter ─────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL   = "google/gemini-2.5-flash-lite"
LLM_CONFIDENCE_THRESHOLD = 0.7
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_config.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: new config.py — PROFILES for 3 personal finance profiles"
```

---

## Task 3: sheets_client.py

**Files:**
- Create: `sheets_client.py`
- Create: `tests/test_sheets_client.py`

Note: Le Google Sheet doit avoir deux onglets créés manuellement avant usage :
- `transactions` avec la ligne 1 : `transaction_id,date,label,amount,category,category_status,confidence,profile,account_id,bank,type`
- `metadata` avec la ligne 1 : `key,value` et la ligne 2 : `last_updated,` (valeur vide)

- [ ] **Step 1: Écrire les tests SheetsClient**

Créer `tests/test_sheets_client.py` :

```python
from unittest.mock import MagicMock, patch
import pytest
from sheets_client import SheetsClient, HEADER


@pytest.fixture
def mock_sheet():
    with patch("sheets_client.gspread") as mock_gspread, \
         patch("sheets_client.Credentials") as mock_creds:

        mock_ws_txs = MagicMock()
        mock_ws_meta = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.worksheet.side_effect = lambda name: (
            mock_ws_txs if name == "transactions" else mock_ws_meta
        )
        mock_gspread.authorize.return_value.open_by_key.return_value = mock_spreadsheet

        client = SheetsClient(sheet_id="FAKE_ID", service_account_path="fake.json")
        yield client, mock_ws_txs, mock_ws_meta


def test_get_existing_ids_empty(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = []
    assert client.get_existing_ids() == set()


def test_get_existing_ids_with_data(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "abc", "date": "2026-06-01"},
        {"transaction_id": "def", "date": "2026-06-02"},
    ]
    assert client.get_existing_ids() == {"abc", "def"}


def test_append_rows_calls_worksheet(mock_sheet):
    client, ws_txs, _ = mock_sheet
    rows = [
        {
            "transaction_id": "abc", "date": "2026-06-01", "label": "Carrefour",
            "amount": -42.5, "category": "alimentation", "category_status": "confirmed",
            "confidence": 0.9, "profile": "jeremy", "account_id": "acc1",
            "bank": "CA", "type": "carte",
        }
    ]
    client.append_rows(rows)
    ws_txs.append_rows.assert_called_once()
    values = ws_txs.append_rows.call_args[0][0]
    assert values[0][0] == "abc"
    assert values[0][3] == -42.5


def test_append_rows_empty_does_nothing(mock_sheet):
    client, ws_txs, _ = mock_sheet
    client.append_rows([])
    ws_txs.append_rows.assert_not_called()


def test_get_transactions_all(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "a", "profile": "jeremy", "amount": -10},
        {"transaction_id": "b", "profile": "manon", "amount": -20},
        {"transaction_id": "c", "profile": "commun", "amount": -30},
    ]
    result = client.get_transactions()
    assert len(result) == 3


def test_get_transactions_by_profile(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "a", "profile": "jeremy", "amount": -10},
        {"transaction_id": "b", "profile": "manon", "amount": -20},
    ]
    result = client.get_transactions(profile="jeremy")
    assert len(result) == 1
    assert result[0]["transaction_id"] == "a"


def test_get_transactions_commun_returns_all(mock_sheet):
    client, ws_txs, _ = mock_sheet
    ws_txs.get_all_records.return_value = [
        {"transaction_id": "a", "profile": "jeremy"},
        {"transaction_id": "b", "profile": "manon"},
        {"transaction_id": "c", "profile": "commun"},
    ]
    result = client.get_transactions(profile="commun")
    assert len(result) == 3


def test_get_last_updated_found(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = [{"key": "last_updated", "value": "2026-06-20T06:00:00"}]
    assert client.get_last_updated() == "2026-06-20T06:00:00"


def test_get_last_updated_not_found(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = []
    assert client.get_last_updated() is None


def test_set_last_updated_updates_existing(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = [{"key": "last_updated", "value": "old"}]
    client.set_last_updated("2026-06-23T06:00:00")
    ws_meta.update_cell.assert_called_once_with(2, 2, "2026-06-23T06:00:00")


def test_set_last_updated_appends_if_missing(mock_sheet):
    client, _, ws_meta = mock_sheet
    ws_meta.get_all_records.return_value = []
    client.set_last_updated("2026-06-23T06:00:00")
    ws_meta.append_row.assert_called_once_with(["last_updated", "2026-06-23T06:00:00"])
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_sheets_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'sheets_client'`

- [ ] **Step 3: Écrire sheets_client.py**

```python
# sheets_client.py
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TRANSACTIONS_WS = "transactions"
METADATA_WS = "metadata"
HEADER = [
    "transaction_id", "date", "label", "amount",
    "category", "category_status", "confidence",
    "profile", "account_id", "bank", "type",
]


class SheetsClient:
    def __init__(self, sheet_id: str, service_account_path: str):
        creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        self._txs  = spreadsheet.worksheet(TRANSACTIONS_WS)
        self._meta = spreadsheet.worksheet(METADATA_WS)

    def get_existing_ids(self) -> set[str]:
        records = self._txs.get_all_records()
        return {r["transaction_id"] for r in records if r.get("transaction_id")}

    def append_rows(self, rows: list[dict]):
        if not rows:
            return
        values = [[r[k] for k in HEADER] for r in rows]
        self._txs.append_rows(values, value_input_option="RAW")

    def get_transactions(self, profile: str | None = None) -> list[dict]:
        records = self._txs.get_all_records()
        if profile and profile != "commun":
            return [r for r in records if r.get("profile") == profile]
        return records

    def get_last_updated(self) -> str | None:
        records = self._meta.get_all_records()
        for r in records:
            if r.get("key") == "last_updated":
                return r.get("value") or None
        return None

    def set_last_updated(self, iso_dt: str):
        records = self._meta.get_all_records()
        for i, r in enumerate(records):
            if r.get("key") == "last_updated":
                self._meta.update_cell(i + 2, 2, iso_dt)
                return
        self._meta.append_row(["last_updated", iso_dt])
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_sheets_client.py -v
```

Expected: 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add sheets_client.py tests/test_sheets_client.py
git commit -m "feat: add SheetsClient — gspread wrapper for transactions + metadata"
```

---

## Task 4: Mise à jour llm_categorizer.py

**Files:**
- Modify: `llm_categorizer.py`
- Modify: `tests/test_llm_categorizer.py` (si existant) ou créer

Le fichier existant a un prompt SCI (loyers, prêts). On le remplace par un prompt finance perso.

- [ ] **Step 1: Écrire les tests pour les nouvelles catégories**

Créer `tests/test_llm_categorizer.py` :

```python
from unittest.mock import patch, MagicMock
from llm_categorizer import categorize_transactions, CATEGORIES, _preprocess


def test_categories_are_personal_finance():
    expected = {"alimentation", "transport", "loisirs", "sante", "shopping", "abonnements", "virement", "divers"}
    assert set(CATEGORIES) == expected


def test_empty_input():
    assert categorize_transactions([]) == []


def test_preprocess_no_cheques():
    txs = [
        {"transaction_id": "1", "label": "CARREFOUR", "date": "2026-06-01", "amount": -42.0},
        {"transaction_id": "2", "label": "SNCF",      "date": "2026-06-02", "amount": -89.0},
    ]
    pre, to_llm = _preprocess(txs)
    assert pre == []
    assert len(to_llm) == 2


def test_fallback_on_llm_failure():
    txs = [{"transaction_id": "1", "label": "TEST", "date": "2026-06-01", "amount": -10.0}]
    with patch("llm_categorizer.requests.post", side_effect=Exception("network error")):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "divers"
    assert result[0]["transaction_id"] == "1"


def test_llm_result_mapped_by_id():
    txs = [{"transaction_id": "abc", "label": "Netflix", "date": "2026-06-01", "amount": -17.99}]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '[{"transaction_id": "abc", "category": "abonnements", "confidence": 0.95}]'}}]
    }
    with patch("llm_categorizer.requests.post", return_value=mock_resp):
        result = categorize_transactions(txs)
    assert result[0]["category"] == "abonnements"
    assert result[0]["confidence"] == 0.95
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_llm_categorizer.py -v
```

Expected: `test_categories_are_personal_finance` FAIL (catégories SCI actuelles)

- [ ] **Step 3: Mettre à jour llm_categorizer.py**

Remplacer le contenu de `llm_categorizer.py` par :

```python
import json
import logging
import requests
import config

log = logging.getLogger("llm_categorizer")

CATEGORIES = ["alimentation", "transport", "loisirs", "sante", "shopping", "abonnements", "virement", "divers"]

SYSTEM_PROMPT = """Tu es un assistant bancaire spécialisé en finances personnelles françaises.
Classe chaque transaction bancaire dans exactement une de ces catégories :
- alimentation  : courses alimentaires, restaurants, cafés, livraisons de repas
- transport     : SNCF, Uber, Lyft, carburant, parking, péages, Vélib, transports en commun
- loisirs       : cinéma, concerts, sports, jeux, livres, culture, voyages, hôtels
- sante         : pharmacie, médecin, dentiste, mutuelle, opticien, parapharmacie
- shopping      : vêtements, électronique, Amazon, FNAC, équipement maison, cosmétiques
- abonnements   : Netflix, Spotify, Canal+, abonnements téléphone/internet, logiciels SaaS
- virement      : virement entre comptes personnels, remboursement entre particuliers
- divers        : tout ce qui ne rentre pas dans les catégories ci-dessus

Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour.
Format : [{"transaction_id": "...", "category": "...", "confidence": 0.0}]
confidence entre 0.0 et 1.0."""


def _preprocess(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    return [], transactions


def _build_prompt(transactions: list[dict]) -> str:
    lines = [
        f"- id={t['transaction_id']} date={t['date']} montant={t['amount']}€ libellé={t['label']}"
        for t in transactions
    ]
    return "Transactions à classifier :\n" + "\n".join(lines)


def _parse_response(raw: str) -> list[dict]:
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


def _fallback(transactions: list[dict]) -> list[dict]:
    return [
        {"transaction_id": t["transaction_id"], "category": "divers", "confidence": 0.0}
        for t in transactions
    ]


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    if not transactions:
        return []

    pre_categorized, to_llm = _preprocess(transactions)
    if not to_llm:
        return pre_categorized

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-dashboard.local",
        "X-Title": "Personal Finance Dashboard",
    }
    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(to_llm)},
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
        return pre_categorized + _fallback(to_llm)

    if resp.status_code != 200:
        log.error(f"LLM error {resp.status_code}: {resp.text[:200]}")
        return pre_categorized + _fallback(to_llm)

    try:
        raw = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        log.error(f"LLM response parse error: {e}")
        return pre_categorized + _fallback(to_llm)

    parsed = _parse_response(raw)
    if not parsed:
        log.warning("LLM returned unparseable response, falling back to divers")
        return pre_categorized + _fallback(to_llm)

    result_map = {r["transaction_id"]: r for r in parsed}
    llm_results = [
        result_map.get(t["transaction_id"], {
            "transaction_id": t["transaction_id"],
            "category": "divers",
            "confidence": 0.0,
        })
        for t in to_llm
    ]
    return pre_categorized + llm_results
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_llm_categorizer.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add llm_categorizer.py tests/test_llm_categorizer.py
git commit -m "feat: update llm_categorizer for personal finance categories"
```

---

## Task 5: ingest.py

**Files:**
- Create: `ingest.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Écrire les tests ingest**

Créer `tests/test_ingest.py` :

```python
import pytest
from ingest import _normalize_transaction, _is_differe_line, _deduplicate


def test_normalize_transaction_basic():
    raw = {
        "id": "tx123",
        "display_date": "2026-06-15T00:00:00",
        "value": -42.5,
        "display_name": "CARREFOUR CITY",
        "name": "CARREFOUR",
    }
    result = _normalize_transaction(raw, account_id="acc1", bank="CA", tx_type="carte", profile="jeremy")
    assert result["transaction_id"] == "tx123"
    assert result["date"] == "2026-06-15"
    assert result["amount"] == -42.5
    assert result["label"] == "CARREFOUR CITY"
    assert result["profile"] == "jeremy"
    assert result["bank"] == "CA"
    assert result["type"] == "carte"
    assert result["category"] == "divers"
    assert result["category_status"] == "pending"


def test_normalize_transaction_fallback_name():
    raw = {"id": "tx1", "date": "2026-06-01", "value": -10.0, "name": "SNCF"}
    result = _normalize_transaction(raw, account_id="acc1", bank="Bourso", tx_type="courant", profile="manon")
    assert result["label"] == "SNCF"
    assert result["date"] == "2026-06-01"


def test_is_differe_line_detects_carte():
    assert _is_differe_line("CARTE VISA DEBIT MENSUEL") is True
    assert _is_differe_line("REMB CARTE FEVRIER") is True


def test_is_differe_line_detects_visa():
    assert _is_differe_line("VISA PREMIER PRELEVEMENT") is True


def test_is_differe_line_ignores_normal():
    assert _is_differe_line("CARREFOUR CITY") is False
    assert _is_differe_line("SNCF BILLET") is False
    assert _is_differe_line("NETFLIX") is False


def test_deduplicate_removes_known_ids():
    rows = [
        {"transaction_id": "a", "amount": -10},
        {"transaction_id": "b", "amount": -20},
        {"transaction_id": "c", "amount": -30},
    ]
    existing = {"a", "c"}
    result = _deduplicate(rows, existing)
    assert len(result) == 1
    assert result[0]["transaction_id"] == "b"


def test_deduplicate_empty_existing():
    rows = [{"transaction_id": "x", "amount": -5}]
    result = _deduplicate(rows, set())
    assert len(result) == 1


def test_deduplicate_all_known():
    rows = [{"transaction_id": "a"}, {"transaction_id": "b"}]
    result = _deduplicate(rows, {"a", "b"})
    assert result == []
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_ingest.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'ingest'`

- [ ] **Step 3: Écrire ingest.py**

```python
# ingest.py
import logging
from datetime import datetime, timezone

import config
from finary_auth import FinaryClient
from llm_categorizer import categorize_transactions
from sheets_client import SheetsClient

log = logging.getLogger("ingest")

# Patterns de libellé sur compte courant CA = prélèvement mensuel différé (double-compte avec carte)
_DIFFERE_PATTERNS = ["CARTE", "VISA"]


def _is_differe_line(label: str) -> bool:
    upper = label.upper()
    return any(p in upper for p in _DIFFERE_PATTERNS)


def _normalize_transaction(raw: dict, account_id: str, bank: str, tx_type: str, profile: str) -> dict:
    return {
        "transaction_id":  str(raw.get("id", "")),
        "date":            (raw.get("display_date") or raw.get("date", ""))[:10],
        "label":           raw.get("display_name") or raw.get("name") or "",
        "amount":          float(raw.get("value", 0)),
        "category":        "divers",
        "category_status": "pending",
        "confidence":      0.0,
        "profile":         profile,
        "account_id":      account_id,
        "bank":            bank,
        "type":            tx_type,
    }


def _deduplicate(rows: list[dict], existing_ids: set[str]) -> list[dict]:
    return [r for r in rows if r["transaction_id"] not in existing_ids]


def _fetch_account_transactions(client: FinaryClient, account: dict, profile: str) -> list[dict]:
    account_id = account["id"]
    bank       = account["bank"]
    tx_type    = account["type"]
    is_ca_courant = bank == "CA" and tx_type == "courant"

    rows = []
    page = 1
    while True:
        batch = client.transactions(account_id, page=page, per_page=100)
        if not batch:
            break
        for raw in batch:
            label = raw.get("display_name") or raw.get("name") or ""
            if is_ca_courant and _is_differe_line(label):
                continue
            rows.append(_normalize_transaction(raw, account_id, bank, tx_type, profile))
        page += 1

    log.info(f"  {profile}/{bank}/{tx_type}: {len(rows)} transactions")
    return rows


def run_ingest():
    """Fetch all profiles from Finary, deduplicate against Sheets, categorize new rows, append."""
    sc     = SheetsClient(config.GOOGLE_SHEETS_ID, config.GOOGLE_SERVICE_ACCOUNT_JSON)
    client = FinaryClient()

    existing_ids = sc.get_existing_ids()
    log.info(f"Existing transactions in Sheets: {len(existing_ids)}")

    all_new_rows: list[dict] = []

    for profile_key, profile_cfg in config.PROFILES.items():
        log.info(f"Fetching profile: {profile_key}")
        for account in profile_cfg["accounts"]:
            rows = _fetch_account_transactions(client, account, profile_key)
            new  = _deduplicate(rows, existing_ids)
            all_new_rows.extend(new)
            existing_ids.update(r["transaction_id"] for r in new)

    if not all_new_rows:
        log.info("No new transactions.")
    else:
        log.info(f"Categorizing {len(all_new_rows)} new transactions...")
        categories = categorize_transactions(all_new_rows)
        cat_map    = {c["transaction_id"]: c for c in categories}
        for row in all_new_rows:
            cat = cat_map.get(row["transaction_id"], {})
            row["category"]        = cat.get("category", "divers")
            row["category_status"] = "confirmed"
            row["confidence"]      = float(cat.get("confidence", 0.0))

        sc.append_rows(all_new_rows)
        log.info(f"Appended {len(all_new_rows)} rows to Sheets.")

    sc.set_last_updated(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    log.info("Ingest complete.")
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

```bash
pytest tests/test_ingest.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add ingest.py tests/test_ingest.py
git commit -m "feat: add ingest.py — fetch Finary, filter différé, deduplicate, write Sheets"
```

---

## Task 6: import_history.py

**Files:**
- Create: `import_history.py`

- [ ] **Step 1: Écrire import_history.py**

```python
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
from finary_auth import FinaryClient

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
```

- [ ] **Step 2: Vérifier la syntaxe du script**

```bash
python3 -c "import ast; ast.parse(open('import_history.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add import_history.py
git commit -m "feat: add import_history.py — one-shot Finary historical import"
```

---

## Task 7: Nouveau main.py

**Files:**
- Rewrite: `main.py`

- [ ] **Step 1: Écrire le nouveau main.py**

```python
# main.py
import csv
import io
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
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
    now      = datetime.now()
    curr_ym  = now.strftime("%Y-%m")
    prev_ym  = (now.replace(day=1) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m")

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
        "profile":       profile,
        "profiles":      {k: v["label"] for k, v in config.PROFILES.items()},
        "transactions":  transactions,
        "last_updated":  last_updated,
        "kpis":          kpis,
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
```

- [ ] **Step 2: Vérifier la syntaxe**

```bash
python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Lancer le serveur localement pour vérifier le démarrage**

```bash
uvicorn main:app --reload --port 8000
```

Expected: `Application startup complete.` sans erreur

Ctrl+C pour arrêter.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: new main.py — profile-based routes + APScheduler daily refresh"
```

---

## Task 8: Nouveau dashboard.html

**Files:**
- Rewrite: `templates/dashboard.html`

- [ ] **Step 1: Écrire le nouveau template**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Finance Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 text-gray-900 p-4 md:p-6 font-sans">

<!-- Header -->
<div class="flex justify-between items-center mb-6">
  <div>
    <h1 class="text-2xl font-bold">Finance Dashboard</h1>
    <p class="text-xs text-gray-400">Dernière mise à jour : {{ last_updated }}</p>
  </div>
  <button id="refresh-btn"
          onclick="triggerRefresh()"
          class="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm hover:bg-gray-700 transition">
    ⟳ Rafraîchir
  </button>
</div>

<!-- Profile tabs -->
<div class="flex gap-2 mb-6">
  {% for key, label in profiles.items() %}
  <a href="/?profile={{ key }}"
     class="px-4 py-2 rounded-lg text-sm font-medium transition
            {% if profile == key %}bg-gray-900 text-white{% else %}bg-white text-gray-600 hover:bg-gray-200{% endif %}">
    {{ label }}
  </a>
  {% endfor %}
</div>

<!-- KPIs -->
<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
  <div class="bg-white rounded-xl p-5 shadow-sm">
    <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">Ce mois</p>
    <p class="text-3xl font-extrabold text-red-600">{{ "%.0f"|format(kpis.current_month) }} €</p>
    <p class="text-xs text-gray-400 mt-1">dépenses {{ now_month }}</p>
  </div>
  <div class="bg-white rounded-xl p-5 shadow-sm">
    <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">Mois précédent</p>
    <p class="text-3xl font-extrabold">{{ "%.0f"|format(kpis.previous_month) }} €</p>
  </div>
  <div class="bg-white rounded-xl p-5 shadow-sm">
    <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">Évolution</p>
    <p class="text-3xl font-extrabold
              {% if kpis.delta_pct > 0 %}text-red-600{% else %}text-green-600{% endif %}">
      {% if kpis.delta_pct > 0 %}+{% endif %}{{ "%.1f"|format(kpis.delta_pct) }} %
    </p>
  </div>
</div>

<!-- Transactions -->
<div class="bg-white rounded-xl shadow-sm overflow-hidden">
  <div class="px-5 py-4 border-b border-gray-100 flex justify-between items-center">
    <h2 class="font-semibold">Transactions</h2>
    <a href="/api/transactions.csv?profile={{ profile }}"
       class="text-xs text-gray-500 hover:text-gray-800 underline">
      Exporter CSV
    </a>
  </div>

  {% if transactions %}
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead class="bg-gray-50 text-xs text-gray-400 uppercase tracking-wide">
        <tr>
          <th class="text-left px-5 py-3">Date</th>
          <th class="text-left px-5 py-3">Libellé</th>
          <th class="text-left px-5 py-3">Catégorie</th>
          <th class="text-left px-5 py-3">Banque</th>
          <th class="text-right px-5 py-3">Montant</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-50">
        {% for t in transactions %}
        <tr class="hover:bg-gray-50 transition">
          <td class="px-5 py-3 whitespace-nowrap text-gray-500">{{ t.date }}</td>
          <td class="px-5 py-3 truncate max-w-xs">{{ t.label }}</td>
          <td class="px-5 py-3">
            <span class="text-xs bg-gray-100 rounded px-2 py-0.5">{{ t.category }}</span>
          </td>
          <td class="px-5 py-3 text-gray-400 text-xs">{{ t.bank }}</td>
          <td class="px-5 py-3 text-right font-medium
                     {% if t.amount|float < 0 %}text-red-600{% else %}text-green-600{% endif %}">
            {{ "%.2f"|format(t.amount|float) }} €
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% else %}
  <p class="px-5 py-8 text-center text-gray-400 text-sm">Aucune transaction. Cliquez sur Rafraîchir.</p>
  {% endif %}
</div>

<script>
async function triggerRefresh() {
  const btn = document.getElementById('refresh-btn');
  btn.textContent = '⏳ En cours…';
  btn.disabled = true;
  try {
    await fetch('/api/refresh', { method: 'POST' });
    setTimeout(() => location.reload(), 3000);
  } catch {
    btn.textContent = '⟳ Rafraîchir';
    btn.disabled = false;
  }
}
</script>

</body>
</html>
```

- [ ] **Step 2: Mettre à jour main.py pour passer `now_month` au template**

Dans `main.py`, dans la route `dashboard()`, ajouter `"now_month"` au context :

```python
return templates.TemplateResponse(request, "dashboard.html", {
    "profile":       profile,
    "profiles":      {k: v["label"] for k, v in config.PROFILES.items()},
    "transactions":  transactions,
    "last_updated":  last_updated,
    "kpis":          kpis,
    "now_month":     datetime.now().strftime("%B %Y"),
})
```

- [ ] **Step 3: Fixer l'import timedelta dans main.py**

Remplacer la ligne `from datetime import datetime` par :

```python
from datetime import datetime, timedelta
```

Et dans `_kpis`, remplacer `__import__("datetime").timedelta` par `timedelta` :

```python
prev_ym = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
```

- [ ] **Step 4: Commit**

```bash
git add templates/dashboard.html main.py
git commit -m "feat: new dashboard — profile tabs, KPIs, transaction list"
```

---

## Task 9: Configuration Google Sheets & smoke test

**Files:**
- Modify: `.env` (si existant) ou créer

Pré-requis : le fichier JSON du service account Google doit exister localement.

- [ ] **Step 1: Ajouter la variable dans .env**

Dans `.env`, ajouter :

```
GOOGLE_SERVICE_ACCOUNT_JSON=/chemin/vers/service_account.json
```

- [ ] **Step 2: Préparer le Google Sheet**

Dans le Google Sheet `1MBriVcatxhQ_kgJK0DHyF6s7Ly5ZZLD7MO4qqLj22aY` :

1. Renommer / créer onglet `transactions` avec la ligne 1 :
   `transaction_id	date	label	amount	category	category_status	confidence	profile	account_id	bank	type`

2. Créer onglet `metadata` avec :
   - Ligne 1 : `key	value`
   - Ligne 2 : `last_updated	` (valeur vide)

3. Partager le sheet avec l'email du service account (rôle Éditeur).

- [ ] **Step 3: Lancer la suite de tests complète**

```bash
pytest tests/ -v
```

Expected: tous les tests PASS (les tests unitaires ne touchent pas le vrai Sheets)

- [ ] **Step 4: Lancer l'import historique**

```bash
python3 import_history.py
```

Expected: logs de progression par profil/compte, `✅ Import historique terminé.`
Vérifier dans Google Sheets que des lignes ont été ajoutées dans l'onglet `transactions`.

- [ ] **Step 5: Démarrer le serveur et vérifier le dashboard**

```bash
uvicorn main:app --reload --port 8000
```

Ouvrir http://localhost:8000 — vérifier :
- 3 onglets profil visibles (Jérémy, Manon, Commun)
- KPIs affichés (même à 0 si pas encore de transactions ce mois)
- Liste des transactions visible
- Bouton Rafraîchir fonctionnel

- [ ] **Step 6: Commit final**

```bash
git add .env.example  # si tu veux ajouter un exemple
git commit -m "chore: env setup, Sheets headers — smoke test OK"
```

---

## Self-Review Checklist

- [x] **Archivage SCI** → Task 1
- [x] **3 profils avec account IDs exacts** → Task 2
- [x] **SheetsClient : get_existing_ids, append_rows, get_transactions, get_last_updated, set_last_updated** → Task 3
- [x] **Filtre différé CA courant** → Task 5 (`_is_differe_line`, appliqué dans `_fetch_account_transactions`)
- [x] **Commun = toutes transactions** → `get_transactions(profile="commun")` retourne tout → Task 3
- [x] **Ingest idempotent (déduplication)** → `_deduplicate` + Task 5
- [x] **Import one-shot** → Task 6
- [x] **APScheduler quotidien** → Task 7
- [x] **Refresh manuel** → `POST /api/refresh` → Task 7
- [x] **KPIs : ce mois / mois précédent / delta %** → `_kpis()` → Tasks 7+8
- [x] **Export CSV par profil** → `GET /api/transactions.csv?profile=` → Task 7
- [x] **Dashboard Tailwind avec onglets** → Task 8
- [x] **LLM catégorisation finance perso** → Task 4
- [x] **Pas de loyers, pas de SCI** → aucune mention dans le nouveau code
