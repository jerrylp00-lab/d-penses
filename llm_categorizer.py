import json
import logging
import requests
import config

log = logging.getLogger("llm_categorizer")

CATEGORIES = ["loyer", "pret_recurrent", "pret_exceptionnel", "recurring", "travaux", "divers"]

SYSTEM_PROMPT = """Tu es un expert bancaire spécialisé en prêts immobiliers pour une SCI française.
Classe chaque transaction bancaire dans exactement une de ces catégories :
- loyer            : virement entrant de 690€, 640€ ou 60€ (loyer locataire)
- pret_recurrent   : mensualité régulière CAMCA (même montant chaque mois)
- pret_exceptionnel: frais CAMCA uniques ou inhabituels (frais de dossier, garanties, intérêts différés, montants non récurrents)
- recurring        : dépense sortante récurrente hors prêt (même libellé et montant approximatif chaque mois)
- travaux          : libellé contenant travaux/artisan/matériaux/rénovation (les chèques CHQ sont déjà traités)
- divers           : tout ce qui ne rentre pas dans les catégories ci-dessus

Les prélèvements dont le libellé contient 'CAMCA' sont liés à un prêt immobilier SCI.
Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour.
Format : [{"transaction_id": "...", "category": "...", "confidence": 0.0}]
confidence entre 0.0 et 1.0."""


def _preprocess(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split transactions: chèques (CHQ/CHEQUE) → travaux auto; rest → LLM."""
    pre_categorized = []
    to_llm = []
    for tx in transactions:
        label_upper = tx.get("label", "").upper()
        if "CHQ" in label_upper or "CHEQUE" in label_upper:
            pre_categorized.append({
                "transaction_id": tx["transaction_id"],
                "category": "travaux",
                "confidence": 1.0,
            })
        else:
            to_llm.append(tx)
    return pre_categorized, to_llm


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


def categorize_transactions(transactions: list[dict]) -> list[dict]:
    """Categorize transactions. Chèques auto-tagged travaux; rest sent to LLM."""
    if not transactions:
        return []

    pre_categorized, to_llm = _preprocess(transactions)

    if not to_llm:
        return pre_categorized

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
    except requests.RequestException as e:
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


def _fallback(transactions: list[dict]) -> list[dict]:
    return [
        {"transaction_id": t["transaction_id"], "category": "divers", "confidence": 0.0}
        for t in transactions
    ]
