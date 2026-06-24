import base64
import random
import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config
from sheets_client import SheetsClient

CATEGORIES = [
    "alimentation", "transport", "loisirs", "sante",
    "shopping", "abonnements", "virement", "divers",
]

CATEGORY_META = {
    "alimentation": {"label": "Alimentation", "emoji": "🍽️"},
    "transport":    {"label": "Transport",     "emoji": "🚇"},
    "loisirs":      {"label": "Loisirs",       "emoji": "🎉"},
    "sante":        {"label": "Santé",         "emoji": "💊"},
    "shopping":     {"label": "Shopping",      "emoji": "🛍️"},
    "abonnements":  {"label": "Abonnements",   "emoji": "📱"},
    "virement":     {"label": "Virements",     "emoji": "💸"},
    "divers":       {"label": "Divers",        "emoji": "📦"},
}

ROAST_PHRASES = {
    "jeremy": [
        "Jérémy a contribué à l'économie locale avec une précision scientifique.",
        "Cette semaine, Jérémy a prouvé que l'argent, c'est fait pour circuler.",
    ],
    "manon": [
        "Manon a fait des emplettes avec la discrétion d'un ninja.",
        "Cette semaine, Manon a soutenu courageusement le commerce de proximité.",
    ],
}

MONTHS_FR = ["jan", "fév", "mar", "avr", "mai", "juin",
             "juil", "août", "sep", "oct", "nov", "déc"]

def _fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_FR[d.month - 1]}"


def get_report_week(reference: date | None = None) -> tuple[date, date]:
    """Retourne (lundi, dimanche) de la semaine ISO précédant la semaine de `reference`."""
    ref = reference or date.today()
    lundi_this_week = ref - timedelta(days=ref.weekday())  # weekday()=0 for Monday
    lundi_s1 = lundi_this_week - timedelta(weeks=1)
    dimanche_s1 = lundi_s1 + timedelta(days=6)
    return lundi_s1, dimanche_s1


def get_prev_week(week_start: date) -> tuple[date, date]:
    """Retourne (lundi, dimanche) de la semaine précédant week_start."""
    lundi_s2 = week_start - timedelta(weeks=1)
    return lundi_s2, lundi_s2 + timedelta(days=6)


def compute_stats(
    transactions: list[dict],
    week_start: date,
    week_end: date,
) -> dict[str, dict]:
    """
    Retourne un dict {categorie: {total, count, highlights}} pour la période donnée.
    - Exclut virement_interne
    - Exclut les crédits (amount >= 0)
    - Filtre par date
    """
    filtered = [
        t for t in transactions
        if (
            t.get("category") != "virement_interne"
            and float(t.get("amount", 0)) < 0
            and week_start <= date.fromisoformat(str(t["date"])[:10]) <= week_end
        )
    ]
    by_cat: dict[str, list] = {}
    for t in filtered:
        cat = t.get("category", "divers")
        by_cat.setdefault(cat, []).append(t)

    result = {}
    for cat, txs in by_cat.items():
        amounts = [abs(float(t["amount"])) for t in txs]
        sorted_txs = sorted(txs, key=lambda t: abs(float(t["amount"])), reverse=True)
        result[cat] = {
            "total":      sum(amounts),
            "count":      len(txs),
            "highlights": [
                {"label": t["label"], "amount": abs(float(t["amount"]))}
                for t in sorted_txs[:2]
            ],
        }
    return result


def compute_delta(current: float, previous: float) -> float | None:
    """Retourne le % de variation entre current et previous. None si previous == 0."""
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def compute_winner(
    stats_jeremy: dict[str, dict],
    stats_manon: dict[str, dict],
) -> tuple[str, float]:
    """Retourne (profile_gagnant, difference_en_euros). Gagnant = qui a le moins dépensé."""
    total_j = sum(s["total"] for s in stats_jeremy.values())
    total_m = sum(s["total"] for s in stats_manon.values())
    if total_j <= total_m:
        return "jeremy", round(total_m - total_j, 2)
    return "manon", round(total_j - total_m, 2)


def get_month_trend(
    transactions: list[dict],
    ref_date: date,
) -> float | None:
    """
    Compare total dépenses du mois en cours (jusqu'à ref_date)
    vs même période du mois précédent.
    Retourne % variation. None si pas de données mois précédent.
    """
    this_month_start = ref_date.replace(day=1)
    prev_month_end   = this_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    day_offset = min(ref_date.day, prev_month_end.day)
    prev_month_same_day = prev_month_start.replace(day=day_offset)

    def _total(start: date, end: date) -> float:
        return sum(
            abs(float(t["amount"]))
            for t in transactions
            if (
                t.get("category") != "virement_interne"
                and float(t.get("amount", 0)) < 0
                and start <= date.fromisoformat(str(t["date"])[:10]) <= end
            )
        )

    current  = _total(this_month_start, ref_date)
    previous = _total(prev_month_start, prev_month_same_day)
    return compute_delta(current, previous)
