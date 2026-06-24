from datetime import date
from report import get_report_week, get_prev_week

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
