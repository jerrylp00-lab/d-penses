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


# Libellés qui indiquent sans ambiguïté un virement entre comptes propres.
# Patterns intentionnellement précis — les noms seuls (LEPETIT, TINNIERE) peuvent
# apparaître dans des libellés tiers (factures EDF, remboursements prêt, notaires).
_VIREMENT_INTERNE_PATTERNS = [
    "ALIMENTATION DU COMPTE",       # "Alimentation du compte courant M LEPETIT..."
    "VIREMENT AUTOMATIQUE M LEPETIT",
    "VIREMENT AUTOMATIQUE TINNIERE",
    "VIR INST VERS JEREMY LEPETIT",
    "VIR INST VERS MANON TINNIERE",
    "VIR INST DE MANON TINNIERE",
    "VIR INST DE JEREMY LEPETIT",
    "VIREMENT DEPUIS BOURSOBANK M LEPETIT J OU MME TINNIERE",
    "INST M. LEPETIT JEREMY",
    "INST MADAME TINNIERE MANON",
    "INST MONSIEUR LEPETIT JEREMY",
    "INST MANON TINNIERE",
    "WEB MADAME TINNIERE MANON",
    "WEB MANON TINNIERE",
    "DE MONSIEUR LEPETIT JEREMY",
    "DE MADAME TINNIERE MANON",
    "M LEPETIT J OU MME TINNIERE",   # libellé virement joint
]


def _preprocess(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    pre, to_llm = [], []
    for tx in transactions:
        upper = tx.get("label", "").upper()
        if any(p in upper for p in _VIREMENT_INTERNE_PATTERNS):
            pre.append({"transaction_id": tx["transaction_id"], "category": "virement_interne", "confidence": 1.0})
        else:
            to_llm.append(tx)
    return pre, to_llm


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


def extract_merchant_names(labels: list[str]) -> dict[str, str]:
    """
    Envoie des libellés bancaires bruts au LLM.
    Retourne {label_brut: nom_marchand_lisible}.
    """
    if not labels:
        return {}

    items = "\n".join(f"- {lb}" for lb in labels)
    prompt = (
        "Tu es un assistant bancaire français. Voici des libellés bruts de transactions "
        "(format CB/RIB/virement). Pour chaque libellé, retourne le nom du marchand ou "
        "établissement réel (restaurant, café, magasin, service…). "
        "Si impossible à identifier, retourne une version courte et lisible du libellé.\n\n"
        "Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour.\n"
        'Format : {"libellé_brut": "Nom Marchand", ...}\n\n'
        f"Libellés :\n{items}"
    )

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://finance-dashboard.local",
        "X-Title": "Personal Finance Dashboard",
    }
    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except Exception as e:
        log.error(f"extract_merchant_names failed: {e}")

    return {lb: lb for lb in labels}


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
