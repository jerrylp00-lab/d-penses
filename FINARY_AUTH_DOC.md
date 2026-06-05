# Finary Auth — Documentation technique

## Contexte

Finary utilise **Clerk** comme système d'authentification (clerk.finary.com).
Le compte est lié à un Apple ID : `2ft7cjmw4f@privaterelay.appleid.com`.

La connexion via email+mdp fonctionne (même avec un compte Apple ID),
mais nécessite un **2FA par email** à la première connexion.

---

## Comment ça marche

### 1. Première connexion (une seule fois)

```
python3 finary_auth.py          # envoie le code OTP par email
python3 finary_auth.py <CODE>   # valide et sauvegarde la session
```

La session est sauvegardée dans `~/.finary_session.json`.

### 2. Reconnexions suivantes (automatiques)

```
python3 finary_auth.py   # ✅ Reconnexion automatique réussie
```

Aucune action requise. La session Clerk dure plusieurs semaines.
Si elle expire, refaire l'étape 1.

---

## Architecture de l'authentification

### Endpoints Clerk utilisés

| Étape | Méthode | URL |
|-------|---------|-----|
| Login email+mdp | POST | `https://clerk.finary.com/v1/client/sign_ins` |
| Envoi code OTP | POST | `.../sign_ins/{id}/prepare_second_factor` |
| Validation OTP | POST | `.../sign_ins/{id}/attempt_second_factor` |
| Refresh JWT | POST | `.../client/sessions/{session_id}/tokens` |

### Ce qui est sauvegardé (`~/.finary_session.json`)

```json
{
  "session_id": "sess_XXXX",
  "cookies": {
    "__client": "VALEUR_HTTPONLY_COOKIE",
    "__client_uat": "TIMESTAMP"
  },
  "saved_at": 1780000000
}
```

Le cookie `__client` (httpOnly) est la clé : il permet de rafraîchir
le JWT indéfiniment sans re-login.

### JWT Clerk

- Durée de vie : **60 secondes**
- Refresh : automatique via `POST /tokens` avec le cookie `__client`
- `FinaryClient._get_jwt()` refresh automatiquement avant chaque appel API

---

## Intégration dans une application

### Installation

```bash
pip install curl_cffi
```

### Usage

```python
from finary_auth import FinaryClient

# Connexion automatique (utilise la session sauvegardée)
client = FinaryClient()

# Récupérer les données
accounts = client.holdings_accounts()
summary  = client.wealth_summary()
txs      = client.transactions(account_id="<uuid>")

# Appel API générique
data = client.get("/users/me/cryptos")
```

### Méthodes disponibles

```python
client.me()                          # Profil utilisateur
client.holdings_accounts()           # Tous les comptes
client.wealth_summary()              # Patrimoine (total worth / net)
client.transactions(account_id, page, per_page)  # Transactions d'un compte
client.cryptos()                     # Cryptos
client.securities()                  # Securities / PEA
client.real_estates()                # Immobilier
client.loans()                       # Prêts
client.get("/users/me/...")          # Appel API libre
```

### Gestion de l'expiration de session

La session Clerk dure plusieurs semaines. Si elle expire :

```python
try:
    client = FinaryClient()
except RuntimeError as e:
    if "SESSION_EXPIRED" in str(e):
        # Refaire la connexion complète
        FinaryClient()          # envoie l'OTP
        FinaryClient("123456")  # valide l'OTP
```

---

## Calcul du patrimoine (logique Finary)

Finary affiche **Total worth = actifs hors cartes bancaires**.

```python
summary = client.wealth_summary()
# {
#   "total_worth": 143609.07,   # = Finary "Total worth"
#   "total_debt":   87859.10,   # prêts
#   "net_worth":    55749.97,   # total_worth - dettes
#   "breakdown": {
#     "actifs": [...],
#     "dettes": [...],
#     "cartes": [...]            # exclus du total_worth
#   }
# }
```

**Règles de classification :**
- 🔴 **Prêt** → slug/nom contient "pret" ou "prêt" → soustrait
- ⚪ **Carte** → slug/nom contient "carte" → exclu du total
- 🟢 **Actif** → tout le reste → additionné

---

## Fichiers

| Fichier | Rôle |
|---------|------|
| `finary_auth.py` | Module principal (auth + client API) |
| `~/.finary_session.json` | Session persistante (ne pas versionner) |
| `~/.finary_otp_state.json` | État temporaire OTP (supprimé après usage) |

---

## Sécurité

- Ne jamais committer `~/.finary_session.json` dans git
- Ajouter `.finary_session.json` au `.gitignore`
- Le mot de passe est hardcodé dans `finary_auth.py` — à externaliser
  via variable d'environnement en production :
  ```python
  FINARY_EMAIL    = os.environ.get("FINARY_EMAIL", "2ft7cjmw4f@privaterelay.appleid.com")
  FINARY_PASSWORD = os.environ.get("FINARY_PASSWORD", "")
  ```
