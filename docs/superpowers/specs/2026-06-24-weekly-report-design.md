# Weekly Expense Report — Design Spec
_Date: 2026-06-24_

## Goal

Envoyer chaque lundi matin un rapport HTML humoristique par email récapitulant les dépenses de la semaine précédente (lundi→dimanche ISO), séparément pour Jérémy et Manon.

---

## Architecture

```
APScheduler (main.py)
  └─ every Monday 08h00 → report.py::generate_and_send()
       ├─ sheets_client.py → fetch S-1 (semaine précédente) + S-2 (pour comparaison)
       ├─ filter par profil (jeremy / manon)
       ├─ compute stats par catégorie
       ├─ render Jinja2 → templates/report_email.html (version jeremy)
       ├─ render Jinja2 → templates/report_email.html (version manon)
       └─ smtplib → 2 mails séparés

Route de preview : GET /report/preview?profile=jeremy
  └─ renvoie le HTML dans le browser, sans envoyer de mail
```

Nouveaux fichiers :
- `report.py` — logique stats + rendu + envoi
- `templates/report_email.html` — template Jinja2 style Wrapped
- `static/report-images/<categorie>.png` — images custom fournies par l'utilisateur

---

## Périodicité & dates

- **Semaine ISO** : lundi 00:00 → dimanche 23:59
- Envoi le **lundi à 08h00** = recap de la semaine précédente
- Exemple : envoi lundi 23 juin → recap du **16 au 22 juin**
- Calcul en Python : `date.today() - timedelta(days=7)` pour trouver le lundi de S-1, puis `+ timedelta(days=6)` pour le dimanche

---

## Structure du rapport HTML

### Header
- Titre : "La semaine de [Prénom]"
- Dates : "16 juin – 22 juin 2025"
- Phrase d'accroche roast personnalisée (générée via template Jinja2, blagues écrites à la main par Jérémy)

### Cards par catégorie (grille 2 colonnes)
Une card par catégorie active la semaine. Catégories couvertes :
`alimentation` `transport` `loisirs` `sante` `shopping` `abonnements` `virement` `divers`

Chaque card contient :
- Image custom `static/report-images/<categorie>.png` (inline base64 dans le mail)
- Nom catégorie
- Total dépensé (€)
- Nombre de transactions
- Delta vs semaine précédente : ▲ +X% ou ▼ −X%
- 1-2 transactions highlights : les 2 plus grosses dépenses de la catégorie (label + montant)

### Section Comparaison Jérémy vs Manon
- Barres horizontales par catégorie (proportionnelles)
- Montants Jérémy / Manon côte à côte
- "Gagnant(e) de la semaine" : celui/celle qui a le moins dépensé au total

### Footer
- Total semaine (hors `virement_interne`)
- Tendance mois en cours vs mois précédent (▲/▼ %)

---

## Email

| Champ | Valeur |
|---|---|
| Expéditeur | `jeremylepetit92@gmail.com` |
| Destinataire Jérémy | `jeremylepetit92@gmail.com` |
| Destinataire Manon | `manon.tinniere@gmail.com` |
| Sujet | `💸 Ta semaine du 16 au 22 juin` |
| Format | `multipart/alternative` — HTML uniquement |
| Images | Inline base64 (pas de lien externe, compatible tous clients mail) |

### Config (config.py)
```python
GMAIL_SENDER = "jeremylepetit92@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
REPORT_RECIPIENTS = {
    "jeremy": "jeremylepetit92@gmail.com",
    "manon": "manon.tinniere@gmail.com",
}
```

### Setup Gmail SMTP
1. Activer 2FA sur le compte Google
2. Générer un App Password : Compte Google → Sécurité → Mots de passe des applications
3. Ajouter `GMAIL_APP_PASSWORD=...` dans les env vars

---

## Données & calculs

- Source : Google Sheets onglet `transactions`
- Filtre semaine : `date >= lundi_S1 AND date <= dimanche_S1`
- Exclusion : `category == "virement_interne"` (comme le dashboard)
- Stats par catégorie : `sum(amount)`, `count`, `min transaction` pour highlights
- Comparaison S-2 : même filtre sur la semaine d'avant pour calculer les deltas %
- Comparaison Jérémy vs Manon : agrégation des deux profils sur S-1

---

## Règles métier

Identiques au dashboard :
- `virement_interne` exclu du total KPI
- `virement` (remboursements, PayPal) compté comme dépense
- Filtre différé déjà appliqué en amont dans `ingest.py` — données Sheets déjà propres

---

## Route de preview

```
GET /report/preview?profile=jeremy
GET /report/preview?profile=manon
```

Retourne le HTML rendu sans envoyer de mail. Permet de valider le rendu avant le premier envoi réel.

---

## Fichiers à créer / modifier

| Fichier | Action |
|---|---|
| `report.py` | Créer — stats, rendu Jinja2, envoi SMTP |
| `templates/report_email.html` | Créer — template HTML Wrapped-style |
| `static/report-images/` | Créer le dossier — images fournies par l'utilisateur |
| `main.py` | Modifier — ajouter job APScheduler lundi 08h00 + route `/report/preview` |
| `config.py` | Modifier — ajouter `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, `REPORT_RECIPIENTS` |
