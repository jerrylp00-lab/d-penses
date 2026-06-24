from datetime import date
from report import get_report_week, get_prev_week

def test_get_report_week_on_monday():
    # Si on appelle le lundi 23 juin 2026, la semaine rapportée est 16-22 juin
    mon = date(2026, 6, 23)
    start, end = get_report_week(reference=mon)
    assert start == date(2026, 6, 16)
    assert end   == date(2026, 6, 22)

def test_get_report_week_midweek():
    # Appelé n'importe quel jour de la semaine du 23 → même résultat
    wed = date(2026, 6, 25)
    start, end = get_report_week(reference=wed)
    assert start == date(2026, 6, 16)
    assert end   == date(2026, 6, 22)

def test_get_prev_week():
    start_s2, end_s2 = get_prev_week(date(2026, 6, 16))
    assert start_s2 == date(2026, 6, 9)
    assert end_s2   == date(2026, 6, 15)
