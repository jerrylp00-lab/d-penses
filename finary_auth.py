"""
finary_auth.py
==============
Module d'authentification Finary — connexion automatique et persistante.

Usage minimal :
    from finary_auth import FinaryClient
    client = FinaryClient()
    data = client.get("/users/me/holdings_accounts")

Première utilisation : demande l'OTP reçu par email (une seule fois).
Ensuite : connexion totalement automatique via la session sauvegardée.

Auteur : généré par Claude — Jeremy Lepetit
"""

import json
import os
import re
import time
import logging
from pathlib import Path
from typing import Any, Optional

from curl_cffi import requests as cffi_requests

# ─── Configuration ────────────────────────────────────────────────────────────

CLERK_ROOT  = "https://clerk.finary.com"
APP_ROOT    = "https://app.finary.com"
API_ROOT    = "https://api.finary.com"

FINARY_EMAIL    = "2ft7cjmw4f@privaterelay.appleid.com"
FINARY_PASSWORD = "Jeremy.Lepetit00"

SESSION_FILE  = Path.home() / ".finary_session.json"
OTP_STATE_FILE = Path.home() / ".finary_otp_state.json"

# Durée de vie du JWT Clerk : 60s. On refresh 10s avant expiry.
JWT_TTL      = 60
JWT_MARGIN   = 10

log = logging.getLogger("finary_auth")

# ─── Helpers cookies ──────────────────────────────────────────────────────────

def _extract_cookies(response) -> dict:
    """Extrait tous les Set-Cookie d'une réponse curl_cffi (y compris httpOnly)."""
    cookies = {}
    for key, val in response.headers.items():
        if key.lower() == "set-cookie":
            m = re.match(r"([^=]+)=([^;]*)", val)
            if m:
                cookies[m.group(1).strip()] = m.group(2).strip()
    return cookies


def _load_session() -> Optional[dict]:
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    env_session = os.environ.get("FINARY_SESSION", "")
    if env_session:
        try:
            return json.loads(env_session)
        except Exception:
            pass
    return None


def _save_session(session_id: str, cookies: dict):
    data = {
        "session_id": session_id,
        "cookies": cookies,
        "saved_at": time.time(),
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    log.debug(f"Session sauvegardée ({SESSION_FILE})")


# ─── Authentification ─────────────────────────────────────────────────────────

def _signin_step1() -> str:
    """
    Étape 1 : email+mdp → envoie le code OTP par email.
    Sauvegarde l'état intermédiaire dans OTP_STATE_FILE.
    Retourne "complete" si pas de 2FA, "otp_sent" sinon.
    """
    session = cffi_requests.Session()
    headers = {
        "Accept-Encoding": "identity",
        "Origin": APP_ROOT,
        "Referer": APP_ROOT,
        "User-Agent": "FinaryDashboard/1.0",
    }

    r1 = session.post(
        f"{CLERK_ROOT}/v1/client/sign_ins",
        data={"identifier": FINARY_EMAIL, "password": FINARY_PASSWORD},
        headers=headers,
        impersonate="chrome110",
    )
    resp        = r1.json()
    all_cookies = _extract_cookies(r1)

    if resp.get("response", {}).get("status") == "complete":
        clerk_session = resp["client"]["sessions"][0]
        state = {
            "session_id": clerk_session["id"],
            "cookies":    all_cookies,
            "complete":   True,
        }
        with open(OTP_STATE_FILE, "w") as f:
            json.dump(state, f)
        return "complete"

    if resp.get("response", {}).get("status") != "needs_second_factor":
        raise RuntimeError(f"Signin failed: {resp.get('errors', resp)}")

    sign_in_id = resp["response"]["id"]
    email_id   = resp["response"]["supported_second_factors"][0]["email_address_id"]

    r2 = session.post(
        f"{CLERK_ROOT}/v1/client/sign_ins/{sign_in_id}/prepare_second_factor",
        data={"strategy": "email_code", "email_address_id": email_id},
        headers=headers,
        impersonate="chrome110",
    )
    all_cookies.update(_extract_cookies(r2))

    with open(OTP_STATE_FILE, "w") as f:
        json.dump({"sign_in_id": sign_in_id, "cookies": all_cookies, "complete": False}, f)

    return "otp_sent"


def _signin_step2(otp_code: str) -> dict:
    """
    Étape 2 : soumet le code OTP et finalise la connexion.
    Retourne {"session_id": ..., "cookies": {...}}
    """
    if not OTP_STATE_FILE.exists():
        raise RuntimeError("Pas d'état OTP trouvé — relancez sans argument d'abord.")

    with open(OTP_STATE_FILE) as f:
        state = json.load(f)

    # Cas sans 2FA (déjà complet à l'étape 1)
    if state.get("complete"):
        OTP_STATE_FILE.unlink(missing_ok=True)
        return {"session_id": state["session_id"], "cookies": state["cookies"]}

    sign_in_id  = state["sign_in_id"]
    all_cookies = state["cookies"]

    headers = {
        "Accept-Encoding": "identity",
        "Origin": APP_ROOT,
        "Referer": APP_ROOT,
        "User-Agent": "FinaryDashboard/1.0",
    }
    session = cffi_requests.Session()
    for name, value in all_cookies.items():
        session.cookies.set(name, value, domain="clerk.finary.com")

    r3 = session.post(
        f"{CLERK_ROOT}/v1/client/sign_ins/{sign_in_id}/attempt_second_factor",
        data={"strategy": "email_code", "code": otp_code},
        headers=headers,
        impersonate="chrome110",
    )
    resp = r3.json()
    all_cookies.update(_extract_cookies(r3))

    if resp.get("response", {}).get("status") != "complete":
        errors = resp.get("errors", [])
        msg    = errors[0].get("long_message", str(errors)) if errors else str(resp)
        raise RuntimeError(f"OTP incorrect ou expiré : {msg}")

    clerk_session = resp["client"]["sessions"][0]
    session_id    = clerk_session["id"]
    OTP_STATE_FILE.unlink(missing_ok=True)
    return {"session_id": session_id, "cookies": all_cookies}


def _refresh_jwt(session_id: str, cookies: dict) -> Optional[str]:
    """
    Rafraîchit le JWT via les cookies de session sauvegardés.
    Retourne le JWT ou None si la session a expiré.
    """
    s = cffi_requests.Session()
    for name, value in cookies.items():
        s.cookies.set(name, value, domain="clerk.finary.com")
    s.impersonate = "chrome110"

    r = s.post(f"{CLERK_ROOT}/v1/client/sessions/{session_id}/tokens")
    if r.status_code == 200:
        return r.json().get("jwt")
    log.warning(f"Token refresh failed: {r.status_code} — {r.text[:200]}")
    return None


# ─── Client principal ─────────────────────────────────────────────────────────

class FinaryClient:
    """
    Client Finary auto-authentifié.

    Exemple :
        client = FinaryClient()
        accounts = client.get("/users/me/holdings_accounts")
        txs = client.get("/users/me/holdings_accounts/<id>/transactions")
    """

    def __init__(self, otp_code: str = ""):
        self._session_id  = None
        self._cookies     = {}
        self._jwt         = None
        self._jwt_fetched = 0.0

        self._init(otp_code)

    def _init(self, otp_code: str = ""):
        """Charge la session depuis le disque ou fait un signin complet."""
        saved = _load_session()

        if saved:
            log.debug("Session trouvée sur disque, tentative de refresh...")
            jwt = _refresh_jwt(saved["session_id"], saved["cookies"])
            if jwt:
                self._session_id  = saved["session_id"]
                self._cookies     = saved["cookies"]
                self._jwt         = jwt
                self._jwt_fetched = time.time()
                log.info("✅ Reconnexion automatique réussie.")
                return
            else:
                log.warning("Session expirée, signin complet requis.")

        # Signin complet en deux étapes
        log.info("Connexion Finary en cours...")

        if otp_code:
            # Étape 2 : on a le code OTP
            result = _signin_step2(otp_code)
        else:
            # Étape 1 : envoyer le code par email
            status = _signin_step1()
            if status == "otp_sent":
                raise RuntimeError(
                    "OTP_REQUIRED: Code envoyé par email. "
                    "Relancez avec otp_code=<code>."
                )
            # complete sans 2FA
            with open(OTP_STATE_FILE) as f:
                result = json.load(f)
            OTP_STATE_FILE.unlink(missing_ok=True)

        self._session_id = result["session_id"]
        self._cookies    = result["cookies"]

        # Obtenir le premier JWT
        jwt = _refresh_jwt(self._session_id, self._cookies)
        if not jwt:
            raise RuntimeError("Impossible d'obtenir un JWT après signin.")

        self._jwt         = jwt
        self._jwt_fetched = time.time()
        _save_session(self._session_id, self._cookies)
        log.info("✅ Connexion réussie et session sauvegardée.")

    def _get_jwt(self) -> str:
        """Retourne un JWT valide, en le rafraîchissant si nécessaire."""
        age = time.time() - self._jwt_fetched
        if age >= (JWT_TTL - JWT_MARGIN):
            log.debug(f"JWT expiré ({age:.0f}s), refresh...")
            jwt = _refresh_jwt(self._session_id, self._cookies)
            if jwt:
                self._jwt         = jwt
                self._jwt_fetched = time.time()
            else:
                # Session expirée → re-signin complet (nécessite OTP)
                raise RuntimeError(
                    "SESSION_EXPIRED: La session Clerk a expiré. "
                    "Relancez FinaryClient(otp_code=<code>) avec le code reçu par email."
                )
        return self._jwt

    def get(self, endpoint: str, **kwargs) -> Any:
        """Effectue un GET sur l'API Finary. Retourne le JSON parsé."""
        jwt = self._get_jwt()
        s   = cffi_requests.Session()
        s.headers.update({"authorization": f"Bearer {jwt}"})
        s.impersonate = "chrome110"
        r = s.get(f"{API_ROOT}{endpoint}", **kwargs)
        r.raise_for_status()
        return r.json()

    def get_result(self, endpoint: str, **kwargs) -> Any:
        """Comme get() mais retourne directement result[]."""
        data = self.get(endpoint, **kwargs)
        return data.get("result", data)

    # ── Raccourcis pratiques ───────────────────────────────────────────────────

    def holdings_accounts(self) -> list:
        return self.get_result("/users/me/holdings_accounts")

    def transactions(self, account_id: str, page: int = 1, per_page: int = 50) -> list:
        return self.get_result(
            f"/users/me/holdings_accounts/{account_id}/transactions",
            params={"page": page, "per_page": per_page},
        )

    def cryptos(self) -> list:
        return self.get_result("/users/me/cryptos")

    def securities(self) -> list:
        return self.get_result("/users/me/securities")

    def real_estates(self) -> list:
        return self.get_result("/users/me/real_estates")

    def loans(self) -> list:
        return self.get_result("/users/me/loans")

    def me(self) -> dict:
        return self.get_result("/users/me")

    def wealth_summary(self) -> dict:
        """
        Calcule le patrimoine comme Finary :
        - total_worth  = actifs hors cartes bancaires
        - total_debt   = prêts
        - net_worth    = total_worth - total_debt
        """
        accounts = self.holdings_accounts()
        LOAN_KW  = ["pret", "prêt"]
        CARD_KW  = ["carte"]

        total_worth = 0.0
        total_debt  = 0.0
        breakdown   = {"actifs": [], "dettes": [], "cartes": []}

        for a in accounts:
            bal  = a.get("balance", 0) or 0
            name = a.get("display_name", "")
            slug = a.get("slug", "").lower()

            is_loan = any(k in slug or k in name.lower() for k in LOAN_KW)
            is_card = any(k in slug or k in name.lower() for k in CARD_KW)

            entry = {"name": name, "balance": bal,
                     "institution": (a.get("institution") or {}).get("name", "?")}

            if is_loan:
                total_debt += bal
                breakdown["dettes"].append(entry)
            elif is_card:
                breakdown["cartes"].append(entry)
            else:
                total_worth += bal
                breakdown["actifs"].append(entry)

        return {
            "total_worth": round(total_worth, 2),
            "total_debt":  round(total_debt,  2),
            "net_worth":   round(total_worth - total_debt, 2),
            "breakdown":   breakdown,
        }


# ─── CLI de test ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    otp = sys.argv[1] if len(sys.argv) > 1 else ""

    try:
        client = FinaryClient(otp_code=otp)
    except RuntimeError as e:
        if "OTP_REQUIRED" in str(e):
            print("\n📧 Code OTP envoyé par email.")
            print("   Relancez : python3 finary_auth.py <CODE>")
            sys.exit(0)
        raise

    print(f"\n✅ Connecté : {client.me().get('firstname')} {client.me().get('lastname')}")

    summary = client.wealth_summary()
    print(f"\n💰 Patrimoine")
    print(f"   Total worth : {summary['total_worth']:>12,.2f} €")
    print(f"   Dettes      : {summary['total_debt']:>12,.2f} €")
    print(f"   Net worth   : {summary['net_worth']:>12,.2f} €")

    print(f"\n📊 Comptes actifs :")
    for a in summary["breakdown"]["actifs"]:
        print(f"   {a['name']:<50} {a['balance']:>10,.2f} €  [{a['institution']}]")

    print(f"\n🔴 Prêts :")
    for a in summary["breakdown"]["dettes"]:
        print(f"   {a['name']:<50} {a['balance']:>10,.2f} €")
