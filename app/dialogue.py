from __future__ import annotations

import re
from typing import Any

from app.config import CATEGORIES, MOYENS_PAIEMENT
from app.formatting import format_montant, parse_date, parse_montant
from app.normalize import normalize_categorie, normalize_moyen

CORRECTION_KEYS = {
    "categorie": "categorie",
    "catégorie": "categorie",
    "category": "categorie",
    "montant": "montant",
    "amount": "montant",
    "prix": "montant",
    "moyen": "moyen_paiement",
    "paiement": "moyen_paiement",
    "moyen_paiement": "moyen_paiement",
    "date": "date",
    "description": "description",
    "desc": "description",
    "libelle": "description",
    "libellé": "description",
    "remboursement": "remboursement",
    "rembourse": "remboursement",
}

KEY_PATTERN = re.compile(
    r"(categorie|catégorie|category|montant|amount|prix|moyen_paiement|moyen|paiement|"
    r"date|description|desc|libelle|libellé|remboursement|rembourse)\s*=\s*",
    flags=re.I,
)


def format_recap(draft: dict[str, Any], *, prefix: str = "Je propose :") -> str:
    montant = draft.get("montant")
    montant_txt = format_montant(montant) if montant is not None else "(à préciser)"
    uncertain = draft.get("uncertain_fields") or []
    warn = ""
    if uncertain:
        warn = f"\nChamps à revoir : {', '.join(uncertain)}"
    cats = ", ".join(CATEGORIES[:8]) + "…"
    return (
        f"{prefix}\n"
        f"\n"
        f"Date : {draft.get('date') or '(à préciser)'}\n"
        f"Description : {draft.get('description') or '(à préciser)'}\n"
        f"Catégorie : {draft.get('categorie') or '(à préciser)'}\n"
        f"Paiement : {draft.get('moyen_paiement') or '(à préciser)'}\n"
        f"Montant : {montant_txt} DH\n"
        f"Remboursement : {draft.get('remboursement') or 'RAS'}"
        f"{warn}\n"
        f"\n"
        f"Réponds OK pour ingérer\n"
        f"ou corrige, ex : montant=800\n"
        f"categorie=Repas Pro\n"
        f"moyen=CB Perso\n"
        f"ou ANNULER\n"
        f"\nCatégories : {cats}"
    )


def is_ok(text: str) -> bool:
    normalized = _compact(text)
    return normalized in {"ok", "oui", "yes", "valide", "valider", "ingere", "ingérer", "ok ingere"}


def is_cancel(text: str) -> bool:
    normalized = _compact(text)
    return normalized in {"annuler", "cancel", "non", "stop", "oublie"}


def is_no_invoice(text: str) -> bool:
    normalized = _compact(text)
    return normalized.startswith("pas de facture") or normalized in {
        "sans facture",
        "nofile",
        "no facture",
    }


def missing_required(draft: dict[str, Any]) -> list[str]:
    missing = []
    if not draft.get("date"):
        missing.append("date")
    if not draft.get("categorie"):
        missing.append("categorie")
    if not draft.get("moyen_paiement"):
        missing.append("moyen")
    if draft.get("montant") is None:
        missing.append("montant")
    return missing


def apply_corrections(draft: dict[str, Any], text: str) -> tuple[dict[str, Any], bool]:
    """Applique les paires clé=valeur. Retourne (draft, found)."""
    updates = parse_corrections(text)
    if not updates:
        return draft, False
    new_draft = dict(draft)
    uncertain = list(new_draft.get("uncertain_fields") or [])
    for key, value in updates.items():
        if key == "montant":
            parsed = parse_montant(value)
            if parsed is not None:
                new_draft["montant"] = parsed
        elif key == "date":
            parsed_date = parse_date(value, current_year=True)
            if parsed_date:
                new_draft["date"] = parsed_date.strftime("%d/%m/%Y")
        elif key == "categorie":
            new_draft["categorie"] = normalize_categorie(value) or value.strip()
        elif key == "moyen_paiement":
            new_draft["moyen_paiement"] = normalize_moyen(value) or "CB Societe"
        elif key == "remboursement":
            new_draft["remboursement"] = "RAS"
        elif key == "description":
            new_draft["description"] = value.strip()
        if key in uncertain:
            uncertain = [u for u in uncertain if u != key]
    new_draft["uncertain_fields"] = uncertain
    return new_draft, True


def parse_corrections(text: str) -> dict[str, str]:
    matches = list(KEY_PATTERN.finditer(text or ""))
    if not matches:
        return {}
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        raw_key = match.group(1).casefold()
        key = CORRECTION_KEYS[raw_key]
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[start:end].strip().strip(",;")
        if value:
            result[key] = value
    return result


def moyens_help() -> str:
    return "Moyens : " + ", ".join(MOYENS_PAIEMENT)


def _compact(text: str) -> str:
    return " ".join((text or "").strip().casefold().replace("é", "e").split())
