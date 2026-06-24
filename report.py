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
