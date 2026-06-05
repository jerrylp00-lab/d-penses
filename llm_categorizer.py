import json
import logging
import requests
import config

log = logging.getLogger("llm_categorizer")

CATEGORIES = ["loyer", "pret", "recurring", "travaux", "divers"]

SYSTEM_PROMPT = """Tu es un assistant comptable pour une SCI immobilière française.
Classe chaque transaction bancaire dans exactement une de ces catégories :
- loyer       : virement entrant de 690€ ou 640€ (loyer locataire)
- pret        : remboursement de prêt bancaire sortant et régulier
- recurring   : dépense sortante récurrente (même libellé et montant approximatif chaque mois)
- travaux     : paiement par chèque OU libellé contenant travaux/artisan/matériaux/rénovation
- divers      : tout ce qui ne rentre pas dans les catégories ci-dessus

Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour.
Format : [{"transaction_id": "...", "category": "...", "confidence": 0.0}]
confidence entre 0.0 et 1.0."""


def _build_prompt(transactions: list[dict]) -> str:
    lines = [f"- id={t['transaction_id']} date={t['date']} montant={t['amount']}€ libellé={t['label']}"
             for t in transactions]
    return "Transactions à classifier :\n" + "\n".join(lines)


def _parse_response(raw: str) -> list[dict]:
    # Strip markdown code fences if present
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


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    """
    Send transactions to OpenRouter LLM for categorization.
    Returns list of {transaction_id, category, confidence}.
    On any failure, returns divers with confidence 0 for all transactions.
    """
    if not transactions:
        return []

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sci-dashboard.local",
        "X-Title": "SCI Dashboard",
    }
    payload = {
        "model": config.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(transactions)},
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
    except requests.RequestException as e:
        log.error(f"LLM request failed: {e}")
        return _fallback(transactions)

    if resp.status_code != 200:
        log.error(f"LLM error {resp.status_code}: {resp.text[:200]}")
        return _fallback(transactions)

    try:
        raw = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        log.error(f"LLM response parse error: {e}")
        return _fallback(transactions)

    parsed = _parse_response(raw)

    if not parsed:
        log.warning("LLM returned unparseable response, falling back to divers")
        return _fallback(transactions)

    # Ensure all transactions have a result; fill missing with divers
    result_map = {r["transaction_id"]: r for r in parsed}
    return [
        result_map.get(t["transaction_id"], {
            "transaction_id": t["transaction_id"],
            "category": "divers",
            "confidence": 0.0,
        })
        for t in transactions
    ]


def _fallback(transactions: list[dict]) -> list[dict]:
    return [
        {"transaction_id": t["transaction_id"], "category": "divers", "confidence": 0.0}
        for t in transactions
    ]
