from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest
from datetime import datetime


MOCK_TRANSACTIONS = [
    # Loyers
    {"record_id": "r1", "transaction_id": "t1", "date": "2026-06-04",
     "amount": 640.0, "label": "LOYER JEAN BART", "category": "loyer",
     "category_status": "confirmed", "confidence": 0.95},
    {"record_id": "r2", "transaction_id": "t2", "date": "2026-05-03",
     "amount": 640.0, "label": "LOYER JEAN BART", "category": "loyer",
     "category_status": "confirmed", "confidence": 0.95},
    {"record_id": "r3", "transaction_id": "t3", "date": "2026-06-02",
     "amount": 690.0, "label": "LOYER VALLABEE", "category": "loyer",
     "category_status": "confirmed", "confidence": 0.95},
    {"record_id": "r4", "transaction_id": "t4", "date": "2026-06-01",
     "amount": 60.0, "label": "LOYER GARAGE", "category": "loyer",
     "category_status": "confirmed", "confidence": 0.95},
    # Prêt
    {"record_id": "r5", "transaction_id": "t5", "date": "2026-06-05",
     "amount": -423.5, "label": "CAMCA MENSUALITE", "category": "pret_recurrent",
     "category_status": "confirmed", "confidence": 0.95},
    {"record_id": "r6", "transaction_id": "t6", "date": "2026-05-05",
     "amount": -423.5, "label": "CAMCA MENSUALITE", "category": "pret_recurrent",
     "category_status": "confirmed", "confidence": 0.95},
    {"record_id": "r7", "transaction_id": "t7", "date": "2025-10-01",
     "amount": -850.0, "label": "CAMCA FRAIS DOSSIER", "category": "pret_exceptionnel",
     "category_status": "confirmed", "confidence": 0.9},
    # Travaux
    {"record_id": "r8", "transaction_id": "t8", "date": "2026-05-15",
     "amount": -1200.0, "label": "CHQ 123456 PLOMBIER", "category": "travaux",
     "category_status": "confirmed", "confidence": 1.0},
    # Récurrentes
    {"record_id": "r9", "transaction_id": "t9", "date": "2026-06-01",
     "amount": -112.0, "label": "ASSURANCE HABITATION", "category": "recurring",
     "category_status": "confirmed", "confidence": 0.88},
    # Divers
    {"record_id": "r10", "transaction_id": "t10", "date": "2026-06-03",
     "amount": -45.0, "label": "DIVERS ACHAT", "category": "divers",
     "category_status": "confirmed", "confidence": 0.6},
]


@pytest.fixture
def mock_deps():
    with patch("main.AirtableClient") as MockAirtable, \
         patch("main.FinaryClient") as MockFinary:

        mock_at = MagicMock()
        MockAirtable.return_value = mock_at
        mock_at.get_last_updated.return_value = datetime(2026, 6, 6)
        mock_at.get_cash.return_value = 8420.0
        mock_at.get_transactions.return_value = MOCK_TRANSACTIONS

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


def test_dashboard_shows_cash(client):
    resp = client.get("/")
    assert "8420" in resp.text or "8 420" in resp.text


def test_dashboard_shows_three_loyer_cards(client):
    resp = client.get("/")
    assert resp.text.count("Appart Jean Bart") >= 1
    assert resp.text.count("Appart Vallabbé") >= 1
    assert resp.text.count("Garage Vallabbé") >= 1


def test_build_dashboard_data_loyer_cards():
    from main import _build_dashboard_data
    data = _build_dashboard_data(MOCK_TRANSACTIONS)
    cards = {c["appart"]: c for c in data["loyer_cards"]}
    assert "Appart Jean Bart" in cards
    assert cards["Appart Jean Bart"]["last_tx"]["amount"] == 640.0
    assert len(cards["Appart Jean Bart"]["all_txs"]) == 2
    assert "Garage Vallabbé" in cards
    assert cards["Garage Vallabbé"]["last_tx"]["amount"] == 60.0


def test_build_dashboard_data_pret():
    from main import _build_dashboard_data
    data = _build_dashboard_data(MOCK_TRANSACTIONS)
    assert len(data["pret_recurrent_all"]) == 2
    assert len(data["pret_exceptionnel_all"]) == 1
    assert len(data["pret_recurrent_last5"]) == 2


def test_export_loyers_csv(client):
    resp = client.get("/export/loyers.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "640" in resp.text


def test_export_travaux_csv(client):
    resp = client.get("/export/travaux.csv")
    assert resp.status_code == 200
    assert "1200" in resp.text or "-1200" in resp.text


def test_export_pret_recurrent_csv(client):
    resp = client.get("/export/pret_recurrent.csv")
    assert resp.status_code == 200
    assert "423" in resp.text


def test_export_pret_exceptionnel_csv(client):
    resp = client.get("/export/pret_exceptionnel.csv")
    assert resp.status_code == 200
    assert "850" in resp.text


def test_export_recurrents_csv(client):
    resp = client.get("/export/recurrents.csv")
    assert resp.status_code == 200
    assert "ASSURANCE" in resp.text


def test_export_transactions_csv(client):
    resp = client.get("/export/transactions.csv")
    assert resp.status_code == 200
    assert "date" in resp.text.lower()


def test_build_dashboard_data_kpis():
    from main import _build_dashboard_data
    # Current month is 2026-06 — recettes = 640+690+60 = 1390, dépenses = 423.5+112+45 = 580.5
    data = _build_dashboard_data(MOCK_TRANSACTIONS)
    assert data["recettes_mois"] == pytest.approx(1390.0)
    assert data["depenses_mois"] == pytest.approx(580.5)
