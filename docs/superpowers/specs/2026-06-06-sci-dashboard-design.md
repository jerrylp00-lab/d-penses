# SCI Dashboard — Design Spec
**Date:** 2026-06-06  
**Statut:** Approuvé

---

## Objectif

Dashboard HTML servi par FastAPI affichant uniquement les transactions du compte SCI Crédit Agricole. Permet de vérifier si les locataires ont payé leur loyer, d'analyser le cash disponible, les dépenses récurrentes, et les travaux.

---

## Stack

- **FastAPI** — backend + sert le HTML
- **finary_auth.py** — client Finary existant, réutilisé inchangé
- **Airtable** — base de données persistante
- **OpenRouter (minimax)** — catégorisation LLM des transactions
- **HTML/JS vanilla** — frontend dashboard

---

## Structure fichiers

```
FINARY/
├── finary_auth.py          # existant, inchangé
├── main.py                 # FastAPI app
├── airtable_client.py      # lecture/écriture Airtable
├── llm_categorizer.py      # appel OpenRouter
├── config.py               # IDs hardcodés
├── find_sci_account.py     # script one-shot setup
├── .env                    # clés API (non versionné)
└── templates/
    └── dashboard.html      # HTML dashboard
```

---

## Architecture & Data Flow

```
Finary API → FastAPI → Airtable → FastAPI → HTML dashboard
```

**Logique refresh :**
1. User ouvre dashboard → FastAPI lit `last_updated` dans Airtable `Metadata`
2. Si `last_updated` > 3 jours (ou refresh manuel) → fetch Finary → écrase table `Transactions` → run LLM → stocke catégories avec status `pending`
3. Sinon → lit Airtable directement
4. Bouton "Rafraîchir" force le refresh peu importe le timestamp

---

## Airtable — Tables

### `Transactions`
| Champ | Type | Notes |
|-------|------|-------|
| `transaction_id` | text | ID Finary |
| `date` | date | |
| `amount` | number | positif = entrant, négatif = sortant |
| `label` | text | libellé brut Finary |
| `category` | text | proposé par LLM |
| `category_status` | select | `pending` / `confirmed` / `rejected` |
| `confidence` | number | score LLM 0-1 |

### `Metadata`
| Champ | Type | Notes |
|-------|------|-------|
| `key` | text | ex: `last_updated` |
| `value` | text | timestamp ISO |

---

## Dashboard HTML — 4 blocs

### ① Loyers — statut locataires
- 2 cartes (un par appart)
- Chaque carte : nom locataire (extrait du libellé transaction), badge **À jour** 🟢 / **En retard** 🔴, montant loyer (690€ ou 640€), total cumulé depuis sept 2025, caution hardcodée
- "En retard" = aucun paiement du bon montant reçu dans le mois courant

### ② Cash disponible
- Solde actuel du compte SCI (depuis `holdings_accounts` Finary, stocké dans `Metadata`)

### ③ Dépenses récurrentes
- Transactions `confirmed` catégorisées `recurring` par le LLM
- Format : libellé + montant mensuel moyen + fréquence détectée
- Remboursements prêt bancaire (`pret`) affichés séparément avec total mensuel

### ④ Travaux & divers
- Transactions `confirmed` catégorisées `travaux`
- Total dépensé en travaux sur la période visible

### Header
- Dernière mise à jour + bouton "Rafraîchir"
- Période couverte (ex: "Sept 2025 → Juin 2026")

### Section "À valider" (bas de page)
- Toutes transactions `pending`
- Affichées en opacité réduite, catégorie en italique
- Par transaction : bouton ✓ (confirmer) + ✗ (rejeter → dropdown recatégorisation)
- Si `confidence` < 0.7 → badge ⚠ visible
- Après validation → `category_status = confirmed`, opacité normale, remonte dans le bon bloc

---

## LLM Catégorisation

**Déclenchement :** uniquement au refresh, pas à chaque page load.

**Catégories :**
- `loyer` — montant 690 ou 640€ entrant
- `pret` — remboursement bancaire sortant régulier
- `recurring` — dépense sortante récurrente (~même montant, ~même libellé chaque mois)
- `travaux` — chèque OU libellé contient travaux/artisan/matériaux
- `divers` — tout le reste

**Input :** liste transactions JSON `[{id, date, amount, label}]`  
**Output :** `[{transaction_id, category, confidence}]` → stocké dans Airtable

**Modèle :** `minimax` via OpenRouter  
**Fallback :** LLM fail → catégorie `divers`, `confidence: 0`, pas de crash

---

## Config hardcodée (`config.py`)

```python
SCI_ACCOUNT_ID = "..."  # trouvé via find_sci_account.py, copié une seule fois

LOYERS = [
    {"montant": 690, "appart": "Appart 1", "caution": 1380, "depuis": "2025-09"},
    {"montant": 640, "appart": "Appart 2", "caution": 1280, "depuis": "2025-09"},
]

CACHE_TTL_DAYS = 3
OPENROUTER_MODEL = "minimax/..."  # slug à confirmer
```

**Variables d'env (`.env`) :**
```
OPENROUTER_API_KEY=...
AIRTABLE_API_KEY=...
AIRTABLE_BASE_ID=...
```

---

## Setup one-shot

`python find_sci_account.py` → liste tous comptes Finary avec noms + IDs → copier l'ID SCI dans `config.py`. Run une seule fois.

---

## Hors scope (phase 2)

- Liaison base locataires
- Historique multi-années
- Notifications loyer en retard
- Validation catégories en masse
