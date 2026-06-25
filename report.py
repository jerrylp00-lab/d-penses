import base64
import logging
import random
from datetime import date, timedelta

from llm_categorizer import extract_merchant_names
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from jinja2 import Environment, FileSystemLoader

import config
from sheets_client import SheetsClient

log = logging.getLogger("report")

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


def get_current_week(reference: date | None = None) -> tuple[date, date]:
    """Retourne (lundi, aujourd'hui) de la semaine en cours."""
    ref = reference or date.today()
    lundi = ref - timedelta(days=ref.weekday())
    return lundi, ref


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
            and t.get("date")
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
                and t.get("date")
                and start <= date.fromisoformat(str(t["date"])[:10]) <= end
            )
        )

    current  = _total(this_month_start, ref_date)
    previous = _total(prev_month_start, prev_month_same_day)
    return compute_delta(current, previous)


def _encode_image(category: str) -> str | None:
    path = Path(__file__).parent / "static" / "report-images" / f"{category}.png"
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode()


def _build_comparison(
    stats_j: dict[str, dict],
    stats_m: dict[str, dict],
) -> dict[str, dict]:
    """
    Construit le dict de comparaison pour le template.
    Inclut uniquement les catégories où au moins un profil a dépensé.
    """
    all_cats = sorted(set(stats_j) | set(stats_m))
    result = {}
    for cat in all_cats:
        total_j = stats_j.get(cat, {}).get("total", 0.0)
        total_m = stats_m.get(cat, {}).get("total", 0.0)
        max_val = max(total_j, total_m, 1)
        meta    = CATEGORY_META.get(cat, {"label": cat, "emoji": "💰"})
        result[cat] = {
            "label":   meta["label"],
            "total_j": total_j,
            "total_m": total_m,
            "pct_j":   round(total_j / max_val * 60),
            "pct_m":   round(total_m / max_val * 60),
        }
    return result


def get_week_merchant_phrase(transactions: list[dict], week_start: date, week_end: date) -> str:
    """
    Trouve le marchand avec le plus de dépenses sur la période.
    Utilise LLM pour nettoyer les libellés bruts.
    """
    filtered = [
        t for t in transactions
        if (
            t.get("category") not in ("virement_interne", "virement")
            and float(t.get("amount", 0)) < 0
            and t.get("date")
            and week_start <= date.fromisoformat(str(t["date"])[:10]) <= week_end
        )
    ]
    if not filtered:
        return "Aucune dépense cette semaine. 🎉"

    unique_labels = list({t["label"] for t in filtered})
    merchant_map = extract_merchant_names(unique_labels)

    by_merchant: dict[str, float] = {}
    for t in filtered:
        merchant = merchant_map.get(t["label"], t["label"])
        by_merchant[merchant] = by_merchant.get(merchant, 0) + abs(float(t["amount"]))

    top = max(by_merchant, key=lambda k: by_merchant[k])
    total = by_merchant[top]
    return f"Tu as bien fait vivre {top} cette semaine avec {total:.0f} € de dépenses chez eux 🏆"


def render_report(
    profile: str,
    stats_current: dict[str, dict],
    stats_prev: dict[str, dict],
    stats_j: dict[str, dict],
    stats_m: dict[str, dict],
    week_start: date,
    week_end: date,
    all_transactions: list[dict],
) -> str:
    """Retourne le HTML du rapport pour `profile`."""
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")), autoescape=True)
    tmpl = env.get_template("report_email.html")

    prenom     = "Jérémy" if profile == "jeremy" else "Manon"
    roast      = random.choice(ROAST_PHRASES.get(profile, ["Bravo pour cette semaine."]))
    week_total = sum(s["total"] for s in stats_current.values())

    # Catégories avec delta vs semaine précédente
    categories = {}
    for cat in CATEGORIES:
        if cat not in stats_current:
            continue
        current_total = stats_current[cat]["total"]
        prev_total    = stats_prev.get(cat, {}).get("total", 0.0)
        meta          = CATEGORY_META.get(cat, {"label": cat, "emoji": "💰"})
        categories[cat] = {
            "label":      meta["label"],
            "emoji":      meta["emoji"],
            "total":      current_total,
            "count":      stats_current[cat]["count"],
            "delta":      compute_delta(current_total, prev_total),
            "highlights": stats_current[cat]["highlights"],
            "img_b64":    _encode_image(cat),
        }

    # Comparaison
    comparison   = _build_comparison(stats_j, stats_m)
    winner, diff = compute_winner(stats_j, stats_m)
    winner_prenom = "Jérémy" if winner == "jeremy" else "Manon"

    # Tendance mois
    month_trend = get_month_trend(all_transactions, week_end)

    # Transactions de la semaine (triées par montant desc)
    week_txs_filtered = sorted(
        [
            t for t in all_transactions
            if (
                t.get("category") not in ("virement_interne", "virement")
                and float(t.get("amount", 0)) < 0
                and t.get("date")
                and week_start <= date.fromisoformat(str(t["date"])[:10]) <= week_end
            )
        ],
        key=lambda t: float(t["amount"]),
    )
    week_txs = [
        {**t, "amount_abs": abs(float(t["amount"])), "date_fmt": t["date"][5:].replace("-", "/")}
        for t in week_txs_filtered
    ]
    week_phrase = get_week_merchant_phrase(all_transactions, week_start, week_end)

    return tmpl.render(
        prenom=prenom,
        week_start=str(week_start),
        week_end=str(week_end),
        week_start_fmt=_fmt_date(week_start),
        week_end_fmt=_fmt_date(week_end),
        roast=roast,
        categories=categories,
        comparison=comparison,
        winner=winner,
        winner_prenom=winner_prenom,
        winner_diff=diff,
        week_total=week_total,
        month_trend=month_trend,
        week_txs=week_txs,
        week_phrase=week_phrase,
    )


def send_html_email(to: str, subject: str, html: str) -> bool:
    """Envoie via Gmail API (OAuth). Returns True on success, False on failure."""
    try:
        creds = Credentials(
            token=None,
            refresh_token=config.GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=config.GMAIL_CLIENT_ID,
            client_secret=config.GMAIL_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        creds.refresh(Request())
        service = build("gmail", "v1", credentials=creds)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = config.GMAIL_SENDER
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        log.error(f"Unexpected error sending to {to}: {e}")
        return False


def generate_and_send(dry_run: bool = False, current_week: bool = False) -> dict[str, str]:
    """
    Génère et envoie les rapports pour jeremy et manon.
    dry_run=True : retourne le HTML sans envoyer de mail (pour /report/preview).
    Retourne un dict {profile: html}.
    """
    if not dry_run and not config.GMAIL_REFRESH_TOKEN:
        log.error("GMAIL_APP_PASSWORD not set — aborting report send")
        return {}

    sc = SheetsClient(config.GOOGLE_SHEETS_ID, config.GOOGLE_SERVICE_ACCOUNT_JSON)
    all_txs = sc.get_transactions()  # tous profils

    week_start, week_end   = get_current_week() if current_week else get_report_week()
    prev_start, prev_end   = get_prev_week(week_start)

    # Stats par profil pour les deux semaines
    txs_j = [t for t in all_txs if t.get("profile") == "jeremy"]
    txs_m = [t for t in all_txs if t.get("profile") == "manon"]

    stats_j_curr = compute_stats(txs_j, week_start, week_end)
    stats_m_curr = compute_stats(txs_m, week_start, week_end)
    stats_j_prev = compute_stats(txs_j, prev_start, prev_end)
    stats_m_prev = compute_stats(txs_m, prev_start, prev_end)

    results = {}
    for profile in config.REPORT_PROFILES:
        stats_curr  = stats_j_curr if profile == "jeremy" else stats_m_curr
        stats_prev  = stats_j_prev if profile == "jeremy" else stats_m_prev
        txs_profile = txs_j        if profile == "jeremy" else txs_m

        html = render_report(
            profile=profile,
            stats_current=stats_curr,
            stats_prev=stats_prev,
            stats_j=stats_j_curr,
            stats_m=stats_m_curr,
            week_start=week_start,
            week_end=week_end,
            all_transactions=txs_profile,
        )
        results[profile] = html

        if not dry_run:
            subject = f"💸 Ta semaine du {_fmt_date(week_start)} au {_fmt_date(week_end)}"
            to      = config.REPORT_RECIPIENTS[profile]
            ok = send_html_email(to, subject, html)
            if ok:
                log.info(f"Report sent to {to}")
            else:
                log.error(f"Failed to send report to {to}")

    return results
