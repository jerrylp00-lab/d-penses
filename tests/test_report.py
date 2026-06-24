import pytest
from datetime import date
from report import get_report_week, get_prev_week, compute_stats, compute_delta, compute_winner, get_month_trend

def test_get_report_week_on_monday():
    # Monday June 22, 2026 → previous week = June 15 (Mon) to June 21 (Sun)
    mon = date(2026, 6, 22)
    start, end = get_report_week(reference=mon)
    assert start == date(2026, 6, 15)
    assert end   == date(2026, 6, 21)

def test_get_report_week_midweek():
    # Wednesday June 24, 2026 (same week as June 22) → same previous week
    wed = date(2026, 6, 24)
    start, end = get_report_week(reference=wed)
    assert start == date(2026, 6, 15)
    assert end   == date(2026, 6, 21)

def test_get_prev_week():
    # Given Monday June 15 → prev week = June 8 (Mon) to June 14 (Sun)
    start_s2, end_s2 = get_prev_week(date(2026, 6, 15))
    assert start_s2 == date(2026, 6, 8)
    assert end_s2   == date(2026, 6, 14)


SAMPLE_TXS = [
    {"date": "2026-06-17", "label": "Carrefour",     "amount": -45.0,  "category": "alimentation", "profile": "jeremy"},
    {"date": "2026-06-18", "label": "Starbucks",     "amount": -6.5,   "category": "alimentation", "profile": "jeremy"},
    {"date": "2026-06-19", "label": "Netflix",       "amount": -17.99, "category": "abonnements",  "profile": "jeremy"},
    {"date": "2026-06-20", "label": "VIR JEREMY",    "amount": -200.0, "category": "virement_interne", "profile": "jeremy"},
    {"date": "2026-06-21", "label": "Salaire",       "amount": 2000.0, "category": "divers",        "profile": "jeremy"},
    {"date": "2026-06-22", "label": "Franprix",      "amount": -12.0,  "category": "alimentation", "profile": "jeremy"},
]
WEEK_START = date(2026, 6, 15)
WEEK_END   = date(2026, 6, 21)


def test_compute_stats_filters_date_and_virement_interne():
    stats = compute_stats(SAMPLE_TXS, WEEK_START, WEEK_END)
    # virement_interne exclu, crédit exclu
    assert "virement_interne" not in stats
    ali = stats["alimentation"]
    assert ali["total"] == pytest.approx(51.5)   # Carrefour(45) + Starbucks(6.5) only; Franprix is June 22 = outside window
    assert ali["count"] == 2
    # top 2 highlights par montant absolu décroissant
    assert ali["highlights"][0]["label"] == "Carrefour"
    assert ali["highlights"][1]["label"] == "Starbucks"

def test_compute_stats_excludes_credits():
    stats = compute_stats(SAMPLE_TXS, WEEK_START, WEEK_END)
    # Salaire (crédit, amount > 0) doit être ignoré
    assert "divers" not in stats

def test_compute_delta_increase():
    assert compute_delta(current=100.0, previous=80.0) == pytest.approx(25.0)

def test_compute_delta_decrease():
    assert compute_delta(current=60.0, previous=80.0) == pytest.approx(-25.0)

def test_compute_delta_no_previous():
    assert compute_delta(current=50.0, previous=0.0) is None

def test_compute_winner():
    stats_j = {"alimentation": {"total": 80.0}, "shopping": {"total": 40.0}}
    stats_m = {"alimentation": {"total": 50.0}, "shopping": {"total": 20.0}}
    winner, diff = compute_winner(stats_j, stats_m)
    assert winner == "manon"
    assert diff == pytest.approx(50.0)

def test_compute_winner_jeremy():
    stats_j = {"alimentation": {"total": 30.0}}
    stats_m = {"alimentation": {"total": 80.0}}
    winner, diff = compute_winner(stats_j, stats_m)
    assert winner == "jeremy"
    assert diff == pytest.approx(50.0)
