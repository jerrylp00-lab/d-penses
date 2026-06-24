import json
import logging
import requests
import config

log = logging.getLogger("llm_categorizer")

CATEGORIES = ["alimentation", "transport", "loisirs", "sante", "shopping", "abonnements", "virement", "virement_interne", "divers"]

SYSTEM_PROMPT = """Tu es un assistant bancaire spécialisé en finances personnelles françaises.
Classe chaque transaction bancaire dans exactement une de ces catégories :
- alimentation     : courses alimentaires, restaurants, cafés, livraisons de repas
- transport        : SNCF, Uber, Lyft, carburant, parking, péages, Vélib, transports en commun
- loisirs          : cinéma, concerts, sports, jeux, livres, culture, voyages, hôtels
- sante            : pharmacie, médecin, dentiste, mutuelle, opticien, parapharmacie
- shopping         : vêtements, électronique, Amazon, FNAC, équipement maison, cosmétiques
- abonnements      : Netflix, Spotify, Canal+, abonnements téléphone/internet, logiciels SaaS
- virement         : paiement PayPal, remboursement à un ami, virement à une tierce personne (compté comme dépense)
- virement_interne : virement entre ses propres comptes — libellé contient LEPETIT, TINNIERE, MANON, JEREMY ou fait référence à un compte courant/épargne personnel (exclu du calcul des dépenses)
- divers           : tout ce qui ne rentre pas dans les catégories ci-dessus

Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour.
Format : [{"transaction_id": "...", "category": "...", "confidence": 0.0}]
confidence entre 0.0 et 1.0."""


def _preprocess(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    return [], transactions


def _build_prompt(transactions: list[dict]) -> str:
    lines = [
        f"- id={t['transaction_id']} date={t['date']} montant={t['amount']}€ libellé={t['label']}"
        for t in transactions
    ]
    return "Transactions à classifier :\n" + "\n".join(lines)


def _parse_response(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def _fallback(transactions: list[dict]) -> list[dict]:
    return [
        {"transaction_id": t["transaction_id"], "category": "divers", "confidence": 0.0}
        for t in transactions
    ]


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    if not transactions:
        return []

    pre_categorized, to_llm = _preprocess(transactions)
    if not to_llm:
        return pre_categorized

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-dashboard.local",
        "X-Title": "Personal Finance Dashboard",
    }
    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(to_llm)},
        ],
        "temperature": 0.1,
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except Exception as e:
        log.error(f"LLM request failed: {e}")
        return pre_categorized + _fallback(to_llm)

    if resp.status_code != 200:
        log.error(f"LLM error {resp.status_code}: {resp.text[:200]}")
        return pre_categorized + _fallback(to_llm)

    try:
        raw = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        log.error(f"LLM response parse error: {e}")
        return pre_categorized + _fallback(to_llm)

    parsed = _parse_response(raw)
    if not parsed:
        log.warning("LLM returned unparseable response, falling back to divers")
        return pre_categorized + _fallback(to_llm)

    result_map = {r["transaction_id"]: r for r in parsed}
    llm_results = [
        result_map.get(t["transaction_id"], {
            "transaction_id": t["transaction_id"],
            "category": "divers",
            "confidence": 0.0,
        })
        for t in to_llm
    ]
    return pre_categorized + llm_results
