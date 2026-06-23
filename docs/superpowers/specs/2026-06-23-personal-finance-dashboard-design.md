# Personal Finance Dashboard — Design Spec
*Date: 2026-06-23*

## Contexte

Remplacement du dashboard SCI (mono-compte, loyers) par un dashboard de dépenses personnelles multi-profils, alimenté par Finary et stocké dans Google Sheets.

L'existant est archivé dans `archive/sci/` et sert de référence pour les patterns FastAPI/FinaryClient.

---

## Profils & Comptes

Trois profils fixes, configurés dans `config.py`.

### Profil Jérémy
| Compte Finary | Banque | Type | ID |
|---|---|---|---|
| COMPTE CHEQUE MONSIEUR LEPETIT JEREMY | Crédit Agricole | courant | `69ce0e7d-4d75-4d59-9094-ed8a7bdc3dac` |
| Carte 513780XXXXXX8282 MR JEREMY LEPETIT | Crédit Agricole | carte | `57696d35-caa7-4c01-ad1f-81e53b9e1627` |
| M LEPETIT JEREMY | BoursoBank | courant | `8bcf1c4f-96f4-4749-9912-2e12bd36aecd` |
| Carte Visa Ultim - MR JEREMY LEPETIT | BoursoBank | carte | `d81f04aa-e9d3-4151-a5af-f91cfd1763dc` |

### Profil Manon
| Compte Finary | Banque | Type | ID |
|---|---|---|---|
| COMPTE CHEQUE MADAME TINNIERE MANON | Crédit Agricole | courant | `8d63155e-5faa-472c-b485-4dd44bb152f6` |
| Carte 513780XXXXXX1658 MME MANON TINNIERE | Crédit Agricole | carte | `6090c538-a57c-4f9f-8de2-0530ad24f043` |
| MME TINNIERE MANON | BoursoBank | courant | `63e50030-33e2-4710-a1a7-297fc0e3715f` |

### Profil Commun
Agrégation de tous les comptes ci-dessus, plus :
| Compte Finary | Banque | Type | ID |
|---|---|---|---|
| M LEPETIT J OU MME TINNI | BoursoBank | courant | `47009a48-082c-446e-ba7e-edc95061b3ee` |
| COMPTE CHEQUE MADAME TINNIERE MANON OU MONSIEUR LEPETIT JEREMY | Crédit Agricole | courant | `b2ad95e5-ac50-4b78-a6b1-a4c35e33e3a8` |

---

## Data Layer

### Google Sheets
- **Sheet ID** : `1MBriVcatxhQ_kgJK0DHyF6s7Ly5ZZLD7MO4qqLj22aY`
- **URL** : https://docs.google.com/spreadsheets/d/1MBriVcatxhQ_kgJK0DHyF6s7Ly5ZZLD7MO4qqLj22aY
- **Auth** : service account JSON (fichier local, chemin dans `.env` → `GOOGLE_SERVICE_ACCOUNT_JSON`)
- **Librairie** : `gspread`

### Onglet `transactions`
Colonnes :
```
transaction_id | date | label | amount | category | category_status | confidence | profile | account_id | bank | type
```
- `profile` : `jeremy` | `manon` | `commun` — le profil auquel appartient la transaction
- `bank` : `CA` | `Bourso`
- `type` : `courant` | `carte`
- `transaction_id` : clé de déduplication (format Finary)

### Onglet `metadata`
```
key | value
last_updated | 2026-06-23T10:00:00
```
Une seule ligne `last_updated` partagée entre tous les profils (refresh global).

### Gestion du différé CA
Sur les comptes de type `courant` Crédit Agricole, les transactions dont le libellé contient `CARTE` ou `VISA` sont ignorées à l'ingest — il s'agit du prélèvement mensuel du différé, déjà capturé transaction par transaction sur le compte `carte`.

---

## Ingest & Refresh

### Import historique (one-shot)
Script `import_history.py` :
1. Pour chaque profil, pour chaque compte : fetch toutes les pages de transactions Finary
2. Filtre différé (courants CA)
3. Déduplique par `transaction_id` contre l'existant dans Sheets
4. Catégorise via LLM les nouvelles transactions
5. Append dans l'onglet `transactions`
6. Met à jour `last_updated` dans `metadata`

### Refresh incrémental
Même logique que l'import historique mais ne fetch que depuis `last_updated`.

Déclenché par :
- **APScheduler** : tâche quotidienne à 06h00 (tous profils d'un coup)
- **Manuel** : `POST /api/refresh` → bouton dans le dashboard

### Catégorisation LLM
- Conservée (même modèle OpenRouter existant)
- Appliquée uniquement aux nouvelles transactions (non encore dans Sheets)
- La catégorie est écrite dans Sheets et modifiable à la main

---

## Routes FastAPI

| Méthode | Route | Description |
|---|---|---|
| GET | `/?profile=commun` | Dashboard (défaut : commun) |
| GET | `/?profile=jeremy` | Dashboard profil Jérémy |
| GET | `/?profile=manon` | Dashboard profil Manon |
| POST | `/api/refresh` | Lance un refresh Finary → Sheets (tous profils) |
| GET | `/api/transactions.csv?profile=...` | Export CSV des transactions du profil |

---

## Dashboard UI

### Navigation
3 onglets en haut : **Jérémy** | **Manon** | **Commun** — navigation via `?profile=`.

### KPIs
- Total dépenses mois en cours
- Total dépenses mois précédent
- Delta % mois/mois

### Liste des transactions
Colonnes : date | libellé | montant | catégorie | banque
Triée par date décroissante.

### Bouton Rafraîchir
Déclenche `POST /api/refresh`, affiche un spinner pendant l'exécution.

---

## Architecture fichiers

```
FINARY/
├── archive/
│   └── sci/              ← tout l'existant déplacé ici
│       ├── main.py
│       ├── config.py
│       ├── airtable_client.py
│       └── templates/dashboard.html
├── config.py             ← nouveau, PROFILES + Google Sheets config
├── main.py               ← nouveau, routes profil-based
├── finary_auth.py        ← inchangé
├── llm_categorizer.py    ← inchangé (ou légèrement adapté)
├── sheets_client.py      ← nouveau, wraps gspread
├── import_history.py     ← nouveau, script one-shot
├── templates/
│   └── dashboard.html    ← nouveau template
└── requirements.txt      ← + gspread, apscheduler
```

---

## Hors scope

- Authentification utilisateur (pas de login)
- Budgets / objectifs par catégorie
- Graphiques (charts) — à envisager plus tard
- Comptes épargne, PEA, prêts
