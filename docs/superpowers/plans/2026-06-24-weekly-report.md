# Weekly Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Envoyer chaque lundi matin un rapport HTML Wrapped-style par email, séparément pour Jérémy et Manon, récapitulant les dépenses de la semaine ISO précédente avec humour et comparaison.

**Architecture:** Script standalone `report.py` appelé par APScheduler dans `main.py` chaque lundi à 08h00. Les stats sont calculées depuis Google Sheets. Le rendu HTML est fait via Jinja2. Envoi par smtplib (Gmail SMTP + App Password). Route `/report/preview` pour valider le rendu sans envoyer.

**Tech Stack:** Python 3.11, FastAPI, APScheduler, Jinja2 (déjà en place), smtplib (stdlib), gspread via `SheetsClient`, pytest.

---

## File Map

| Fichier | Action | Responsabilité |
|---|---|---|
| `config.py` | Modifier | Ajouter constantes Gmail |
| `report.py` | Créer | Dates, stats, rendu, envoi SMTP |
| `templates/report_email.html` | Créer | Template HTML Wrapped-style |
| `static/report-images/` | Créer dossier | Images catégories (fournies par l'utilisateur) |
| `main.py` | Modifier | Job APScheduler lundi 08h00 + route `/report/preview` |
| `tests/test_report.py` | Créer | Tests unitaires stats + dates |

---

## Task 1: Config Gmail

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Ajouter les constantes Gmail dans config.py**

Ajouter à la fin de `config.py` :

```python
# ── Report Email ───────────────────────────────────────────────────────────────
GMAIL_SENDER      = "jeremylepetit92@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
REPORT_RECIPIENTS = {
    "jeremy": "jeremylepetit92@gmail.com",
    "manon":  "manon.tinniere@gmail.com",
}
REPORT_PROFILES   = ["jeremy", "manon"]
```

- [ ] **Step 2: Commit**

```bash
git add config.py
git commit -m "feat: add Gmail SMTP config for weekly report"
```

---

## Task 2: Date utilities

**Files:**
- Create: `report.py` (partie 1 — fonctions date)
- Create: `tests/test_report.py`

- [ ] **Step 1: Écrire les tests date**

Créer `tests/test_report.py` :

```python
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
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd /Users/jeremylepetit/FINARY && python -m pytest tests/test_report.py -v 2>&1 | head -20
```
Attendu : `ImportError` ou `ModuleNotFoundError`.

- [ ] **Step 3: Créer report.py avec les fonctions date**

```python
# report.py
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


def get_report_week(reference: date | None = None) -> tuple[date, date]:
    """Retourne (lundi, dimanche) de la semaine ISO précédant la semaine de `reference`."""
    ref = reference or date.today()
    lundi_this_week = ref - timedelta(days=ref.weekday())
    lundi_s1 = lundi_this_week - timedelta(weeks=1)
    dimanche_s1 = lundi_s1 + timedelta(days=6)
    return lundi_s1, dimanche_s1


def get_prev_week(week_start: date) -> tuple[date, date]:
    """Retourne (lundi, dimanche) de la semaine précédant week_start."""
    lundi_s2 = week_start - timedelta(weeks=1)
    return lundi_s2, lundi_s2 + timedelta(days=6)
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
python -m pytest tests/test_report.py::test_get_report_week_on_monday tests/test_report.py::test_get_report_week_midweek tests/test_report.py::test_get_prev_week -v
```
Attendu : 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add report.py tests/test_report.py
git commit -m "feat: report.py date utilities + tests"
```

---

## Task 3: Stats computation

**Files:**
- Modify: `report.py` (ajouter fonctions stats)
- Modify: `tests/test_report.py` (ajouter tests stats)

Format transaction depuis Sheets (déjà normalisé par `ingest.py`) :
```
{"transaction_id": str, "date": "YYYY-MM-DD", "label": str, "amount": float,
 "category": str, "profile": str, "bank": str, "type": str, ...}
```
Les dépenses ont `amount < 0`. Les crédits ont `amount > 0`.

- [ ] **Step 1: Écrire les tests stats**

Ajouter dans `tests/test_report.py` :

```python
from report import compute_stats, compute_delta, compute_winner, get_month_trend

SAMPLE_TXS = [
    {"date": "2026-06-17", "label": "Carrefour",     "amount": -45.0,  "category": "alimentation", "profile": "jeremy"},
    {"date": "2026-06-18", "label": "Starbucks",     "amount": -6.5,   "category": "alimentation", "profile": "jeremy"},
    {"date": "2026-06-19", "label": "Netflix",       "amount": -17.99, "category": "abonnements",  "profile": "jeremy"},
    {"date": "2026-06-20", "label": "VIR JEREMY",    "amount": -200.0, "category": "virement_interne", "profile": "jeremy"},
    {"date": "2026-06-21", "label": "Salaire",       "amount": 2000.0, "category": "divers",        "profile": "jeremy"},
    {"date": "2026-06-22", "label": "Franprix",      "amount": -12.0,  "category": "alimentation", "profile": "jeremy"},
]
WEEK_START = date(2026, 6, 16)
WEEK_END   = date(2026, 6, 22)


def test_compute_stats_filters_date_and_virement_interne():
    stats = compute_stats(SAMPLE_TXS, WEEK_START, WEEK_END)
    # virement_interne exclu, crédit exclu
    assert "virement_interne" not in stats
    ali = stats["alimentation"]
    assert ali["total"] == pytest.approx(63.5)
    assert ali["count"] == 3
    # top 2 highlights par montant absolu décroissant
    assert ali["highlights"][0]["label"] == "Carrefour"
    assert ali["highlights"][1]["label"] == "Franprix"

def test_compute_stats_excludes_credits():
    stats = compute_stats(SAMPLE_TXS, WEEK_START, WEEK_END)
    # Salaire (crédit) ignoré
    if "divers" in stats:
        assert stats["divers"]["total"] == pytest.approx(0.0)

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
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
python -m pytest tests/test_report.py -k "stats or delta or winner" -v 2>&1 | head -30
```
Attendu : `ImportError` sur `compute_stats`.

- [ ] **Step 3: Implémenter les fonctions stats dans report.py**

Ajouter après `get_prev_week` dans `report.py` :

```python
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
    Compare total dépenses du mois en cours (jusqu'à aujourd'hui)
    vs même période du mois précédent.
    Retourne % variation. None si pas de données mois précédent.
    """
    this_month_start = ref_date.replace(day=1)
    prev_month_end   = this_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    # Même nb de jours pour comparaison équitable
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
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
python -m pytest tests/test_report.py -v
```
Attendu : tous les tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add report.py tests/test_report.py
git commit -m "feat: report stats computation — compute_stats, delta, winner, month trend"
```

---

## Task 4: HTML email template

**Files:**
- Create: `templates/report_email.html`
- Create: `static/report-images/.gitkeep`

- [ ] **Step 1: Créer le dossier static/report-images**

```bash
mkdir -p /Users/jeremylepetit/FINARY/static/report-images
touch /Users/jeremylepetit/FINARY/static/report-images/.gitkeep
```

- [ ] **Step 2: Créer templates/report_email.html**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ prenom }} — semaine du {{ week_start }} au {{ week_end }}</title>
<style>
  body { margin: 0; padding: 0; background: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  .wrap { max-width: 600px; margin: 0 auto; padding: 24px 16px; }
  .header { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 24px; margin-bottom: 16px; text-align: center; }
  .header-label { font-size: 11px; color: #999; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 6px; }
  .header-name { font-size: 24px; font-weight: 600; color: #111; margin-bottom: 4px; }
  .header-dates { font-size: 13px; color: #666; margin-bottom: 16px; }
  .roast { font-size: 14px; color: #555; font-style: italic; border-left: 3px solid #ddd; padding-left: 12px; text-align: left; }
  .section-label { font-size: 11px; font-weight: 600; color: #999; letter-spacing: 0.1em; text-transform: uppercase; margin: 20px 0 8px; }
  .cards-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .cat-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; overflow: hidden; }
  .cat-img { width: 100%; height: 90px; object-fit: cover; display: block; }
  .cat-img-placeholder { width: 100%; height: 90px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 36px; }
  .cat-body { padding: 12px; }
  .cat-name { font-size: 11px; font-weight: 600; color: #999; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
  .cat-amount { font-size: 22px; font-weight: 600; color: #111; margin-bottom: 2px; }
  .cat-meta { font-size: 12px; color: #888; margin-bottom: 8px; }
  .cat-delta { font-size: 12px; font-weight: 600; display: inline-block; padding: 2px 8px; border-radius: 20px; }
  .delta-up { background: #fef2f2; color: #dc2626; }
  .delta-down { background: #f0fdf4; color: #16a34a; }
  .delta-none { background: #f5f5f5; color: #888; }
  .cat-highlights { margin-top: 10px; padding-top: 10px; border-top: 1px solid #f0f0f0; }
  .highlight-row { font-size: 12px; color: #555; margin-bottom: 3px; display: flex; justify-content: space-between; }
  .compare-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 16px; margin-top: 8px; }
  .legend { display: flex; gap: 16px; margin-bottom: 14px; }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; vertical-align: middle; }
  .legend-text { font-size: 13px; color: #555; }
  .compare-row { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .compare-label { font-size: 12px; color: #888; width: 90px; flex-shrink: 0; }
  .bars { flex: 1; display: flex; gap: 3px; align-items: center; }
  .bar { height: 8px; border-radius: 4px; min-width: 4px; }
  .bar-j { background: #7c3aed; }
  .bar-m { background: #db2777; }
  .bar-amounts { font-size: 11px; color: #555; min-width: 70px; text-align: right; }
  .winner-box { display: flex; align-items: center; gap: 8px; padding: 10px 12px; background: #f0fdf4; border-radius: 8px; margin-top: 12px; }
  .winner-text { font-size: 13px; font-weight: 600; color: #166534; }
  .footer-card { background: #fff; border: 1px solid #e5e5e5; border-radius: 12px; padding: 16px; margin-top: 16px; display: flex; justify-content: space-between; align-items: center; }
  .footer-total-label { font-size: 12px; color: #888; margin-bottom: 4px; }
  .footer-total { font-size: 24px; font-weight: 600; color: #111; }
  .footer-trend-label { font-size: 12px; color: #888; margin-bottom: 4px; text-align: right; }
  .footer-trend { font-size: 16px; font-weight: 600; text-align: right; }
  .trend-up { color: #dc2626; }
  .trend-down { color: #16a34a; }
  .trend-none { color: #888; }
</style>
</head>
<body>
<div class="wrap">

  <!-- HEADER -->
  <div class="header">
    <div class="header-label">Rapport hebdo</div>
    <div class="header-name">La semaine de {{ prenom }} 💸</div>
    <div class="header-dates">{{ week_start_fmt }} – {{ week_end_fmt }}</div>
    <div class="roast">{{ roast }}</div>
  </div>

  <!-- CATÉGORIES -->
  <div class="section-label">Par catégorie</div>
  <div class="cards-grid">
    {% for cat, data in categories.items() %}
    <div class="cat-card">
      {% if data.img_b64 %}
        <img class="cat-img" src="data:image/png;base64,{{ data.img_b64 }}" alt="{{ data.label }}">
      {% else %}
        <div class="cat-img-placeholder">{{ data.emoji }}</div>
      {% endif %}
      <div class="cat-body">
        <div class="cat-name">{{ data.label }}</div>
        <div class="cat-amount">{{ "%.0f"|format(data.total) }} €</div>
        <div class="cat-meta">{{ data.count }} transaction{{ "s" if data.count > 1 else "" }}</div>
        {% if data.delta is not none %}
          {% if data.delta > 0 %}
            <span class="cat-delta delta-up">▲ +{{ "%.0f"|format(data.delta) }}%</span>
          {% elif data.delta < 0 %}
            <span class="cat-delta delta-down">▼ {{ "%.0f"|format(data.delta) }}%</span>
          {% else %}
            <span class="cat-delta delta-none">= stable</span>
          {% endif %}
        {% else %}
          <span class="cat-delta delta-none">nouveau</span>
        {% endif %}
        {% if data.highlights %}
        <div class="cat-highlights">
          {% for h in data.highlights %}
          <div class="highlight-row">
            <span>{{ h.label[:28] }}{% if h.label|length > 28 %}…{% endif %}</span>
            <span>{{ "%.0f"|format(h.amount) }} €</span>
          </div>
          {% endfor %}
        </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- COMPARAISON -->
  <div class="section-label">Jérémy vs Manon</div>
  <div class="compare-card">
    <div class="legend">
      <span><span class="legend-dot" style="background:#7c3aed"></span><span class="legend-text">Jérémy</span></span>
      <span><span class="legend-dot" style="background:#db2777"></span><span class="legend-text">Manon</span></span>
    </div>
    {% for cat, data in comparison.items() %}
    <div class="compare-row">
      <div class="compare-label">{{ data.label }}</div>
      <div class="bars">
        <div class="bar bar-j" style="width:{{ data.pct_j }}%"></div>
        <div class="bar bar-m" style="width:{{ data.pct_m }}%"></div>
      </div>
      <div class="bar-amounts">{{ "%.0f"|format(data.total_j) }} / {{ "%.0f"|format(data.total_m) }} €</div>
    </div>
    {% endfor %}
    <div class="winner-box">
      🏆 <div class="winner-text">Gagnant{{ "e" if winner == "manon" else "" }} : {{ winner_prenom }} (−{{ "%.0f"|format(winner_diff) }} €)</div>
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer-card">
    <div>
      <div class="footer-total-label">Total semaine</div>
      <div class="footer-total">{{ "%.0f"|format(week_total) }} €</div>
    </div>
    <div>
      <div class="footer-trend-label">vs mois dernier</div>
      {% if month_trend is not none %}
        {% if month_trend > 0 %}
          <div class="footer-trend trend-up">▲ +{{ "%.0f"|format(month_trend) }}%</div>
        {% elif month_trend < 0 %}
          <div class="footer-trend trend-down">▼ {{ "%.0f"|format(month_trend) }}%</div>
        {% else %}
          <div class="footer-trend trend-none">= stable</div>
        {% endif %}
      {% else %}
        <div class="footer-trend trend-none">—</div>
      {% endif %}
    </div>
  </div>

</div>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add templates/report_email.html static/report-images/.gitkeep
git commit -m "feat: Wrapped-style HTML email template + static/report-images dir"
```

---

## Task 5: Rendering function

**Files:**
- Modify: `report.py` (ajouter `render_report` et `_encode_image`)

- [ ] **Step 1: Ajouter `_encode_image` et `render_report` dans report.py**

Ajouter après les fonctions stats :

```python
MONTHS_FR = ["jan", "fév", "mar", "avr", "mai", "juin",
             "juil", "août", "sep", "oct", "nov", "déc"]

def _fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_FR[d.month - 1]}"


def _encode_image(category: str) -> str | None:
    path = Path(f"static/report-images/{category}.png")
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
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
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
    )
```

- [ ] **Step 2: Commit**

```bash
git add report.py
git commit -m "feat: render_report — Jinja2 rendering with stats, comparison, month trend"
```

---

## Task 6: SMTP sending + orchestration

**Files:**
- Modify: `report.py` (ajouter `send_html_email` et `generate_and_send`)

- [ ] **Step 1: Ajouter `send_html_email` dans report.py**

```python
def send_html_email(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.GMAIL_SENDER
    msg["To"]      = to
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_SENDER, to, msg.as_string())
```

- [ ] **Step 2: Ajouter `generate_and_send` dans report.py**

```python
def generate_and_send(dry_run: bool = False) -> dict[str, str]:
    """
    Génère et envoie les rapports pour jeremy et manon.
    dry_run=True : retourne le HTML sans envoyer de mail (pour /report/preview).
    Retourne un dict {profile: html}.
    """
    import logging
    log = logging.getLogger("report")

    sc = SheetsClient(config.GOOGLE_SHEETS_ID, config.GOOGLE_SERVICE_ACCOUNT_JSON)
    all_txs = sc.get_transactions()  # tous profils

    week_start, week_end   = get_report_week()
    prev_start, prev_end   = get_prev_week(week_start)

    # Stats par profil pour les deux semaines
    txs_j_curr = [t for t in all_txs if t.get("profile") == "jeremy"]
    txs_m_curr = [t for t in all_txs if t.get("profile") == "manon"]

    stats_j_curr = compute_stats(txs_j_curr, week_start, week_end)
    stats_m_curr = compute_stats(txs_m_curr, week_start, week_end)
    stats_j_prev = compute_stats(txs_j_curr, prev_start, prev_end)
    stats_m_prev = compute_stats(txs_m_curr, prev_start, prev_end)

    results = {}
    for profile in config.REPORT_PROFILES:
        stats_curr = stats_j_curr if profile == "jeremy" else stats_m_curr
        stats_prev = stats_j_prev if profile == "jeremy" else stats_m_prev
        txs_profile = txs_j_curr if profile == "jeremy" else txs_m_curr

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
            send_html_email(to, subject, html)
            log.info(f"Report sent to {to}")

    return results
```

- [ ] **Step 3: Commit**

```bash
git add report.py
git commit -m "feat: send_html_email + generate_and_send orchestration"
```

---

## Task 7: main.py — APScheduler + /report/preview

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Ajouter import + job APScheduler**

Dans `main.py`, ajouter l'import :
```python
from report import generate_and_send
```

Après la ligne `scheduler.add_job(run_ingest, ...)`, ajouter :
```python
scheduler.add_job(generate_and_send, "cron", day_of_week="mon", hour=8, minute=0, id="weekly_report")
```

- [ ] **Step 2: Ajouter la route /report/preview**

Ajouter à la fin de `main.py` :

```python
@app.get("/report/preview", response_class=HTMLResponse)
def report_preview(profile: str = "jeremy"):
    if profile not in config.REPORT_PROFILES:
        profile = "jeremy"
    results = generate_and_send(dry_run=True)
    return HTMLResponse(content=results[profile])
```

- [ ] **Step 3: Vérifier que l'app démarre sans erreur**

```bash
cd /Users/jeremylepetit/FINARY && uvicorn main:app --port 8001 --reload 2>&1 | head -20
```
Attendu : `Application startup complete.` sans erreur.

- [ ] **Step 4: Tester la route preview**

Ouvrir dans le browser : `http://localhost:8001/report/preview?profile=jeremy`

Vérifier que le rapport s'affiche correctement avec les vraies données.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: APScheduler weekly report job + /report/preview route"
```

---

## Task 8: Variables d'environnement Gmail

**Files:**
- Aucun fichier code — configuration manuelle.

- [ ] **Step 1: Générer un App Password Gmail**

1. Aller sur [myaccount.google.com/security](https://myaccount.google.com/security)
2. S'assurer que la 2FA est activée sur `jeremylepetit92@gmail.com`
3. Chercher "Mots de passe des applications" (ou App Passwords)
4. Créer un mot de passe pour l'app "Mail" / "Autre (nom personnalisé)" → nommer "FINARY"
5. Copier le mot de passe généré (16 caractères)

- [ ] **Step 2: Ajouter dans .env ou l'environnement**

```bash
# Ajouter à ~/.zshrc ou au fichier .env du projet
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
```

- [ ] **Step 3: Tester l'envoi réel**

```bash
cd /Users/jeremylepetit/FINARY && python -c "
from report import generate_and_send
generate_and_send(dry_run=False)
print('Mails envoyés.')
"
```
Attendu : `Mails envoyés.` + 2 mails reçus (jeremy + manon).

- [ ] **Step 4: Ajouter les images catégories**

Déposer les images générées dans `static/report-images/` avec ces noms exacts :
- `alimentation.png`
- `transport.png`
- `loisirs.png`
- `sante.png`
- `shopping.png`
- `abonnements.png`
- `virement.png`
- `divers.png`

Sans image, le template affiche l'emoji à la place — le rapport reste fonctionnel.
