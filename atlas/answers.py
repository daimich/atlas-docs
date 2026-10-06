"""Evidence mode and an optional Ollama adapter with quote validation."""

from .models import generate_claims


def validate_claims(payload, evidence):
    if not isinstance(payload, dict) or type(payload.get("abstain")) is not bool:
        raise ValueError("Generator must return an abstain boolean")
    claims = payload.get("claims")
    if not isinstance(claims, list) or len(claims) > 8:
        raise ValueError("Generator must return at most eight claims")
    if payload["abstain"]:
        if claims:
            raise ValueError("Abstention must not contain claims")
        return []
    if not claims:
        raise ValueError("Answer must contain cited claims")
    allowed = {r["id"]: r for r in evidence}
    validated = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Invalid claim")
        identifier, quote, text = (claim.get(k) for k in ("citation", "quote", "text"))
        if not all(isinstance(v, str) for v in (identifier, quote, text)):
            raise ValueError("Claim fields must be strings")
        if identifier not in allowed or not quote.strip() or quote not in allowed[identifier]["text"]:
            raise ValueError("Generator returned an unknown citation or fabricated quote")
        if not text.strip() or len(text) > 1500:
            raise ValueError("Invalid claim text")
        validated.append(dict(claim, name=allowed[identifier]["name"], page=allowed[identifier]["page"]))
    return validated


def answer(question, hits, model=None, endpoint="http://localhost:11434"):
    evidence = [{k: r[k] for k in ("id", "name", "page", "text")} for r in hits]
    if not evidence:
        return {"mode": "evidence", "abstained": True, "claims": [], "evidence": []}
    if not model:
        return {"mode": "evidence", "abstained": False,
                "claims": [{"text": "Retrieved passage", "quote": r["text"], "citation": r["id"],
                            "name": r["name"], "page": r["page"]} for r in evidence], "evidence": evidence}
    payload = generate_claims(question, evidence, model, endpoint)
    claims = validate_claims(payload, evidence)
    return {"mode": "ollama", "abstained": payload["abstain"], "claims": claims, "evidence": evidence}
