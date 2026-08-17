from __future__ import annotations

import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from app.config import CATEGORIES, DRIVE_FOLDER_BY_CATEGORY, MOYENS_PAIEMENT, get_settings
from app.formatting import parse_date, parse_montant, today_casablanca
from app.normalize import normalize_categorie, normalize_moyen

logger = logging.getLogger(__name__)


def extract_invoice(media: bytes, mime: str, user_hint: str = "") -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY manquant. Crée une clé Free sur Google AI Studio.")

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _build_prompt(user_hint)
    part = types.Part.from_bytes(data=media, mime_type=mime)
    config = types.GenerateContentConfig(
        temperature=0.1,
        response_mime_type="application/json",
    )

    last_error: Exception | None = None
    models = [
        settings.gemini_model or "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3-flash-preview",
    ]
    seen: set[str] = set()
    for name in models:
        if name in seen:
            continue
        seen.add(name)
        try:
            response = client.models.generate_content(
                model=name,
                contents=[prompt, part],
                config=config,
            )
            parsed = _parse_model_json(response.text or "")
            return _normalize_extraction(parsed)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("Gemini %s a échoué : %s", name, exc)
            continue
    raise RuntimeError(f"Extraction Gemini impossible : {last_error}") from last_error


def empty_draft(today_str: str) -> dict[str, Any]:
    return {
        "date": today_str,
        "description": "",
        "categorie": None,
        "moyen_paiement": "CB Societe",
        "montant": None,
        "remboursement": "RAS",
        "confidence": 0.0,
        "uncertain_fields": ["categorie", "montant"],
        "has_file": False,
    }


def _build_prompt(user_hint: str) -> str:
    hint = f"\nIndication de l'utilisateur : {user_hint}\n" if user_hint else ""
    return f"""Tu lis une facture / ticket / reçu marocain (MAD / DH).
Réponds UNIQUEMENT en JSON valide, sans markdown.
{hint}
Champs :
- date : jour et mois de la facture au format JJ/MM/AAAA. L'année est TOUJOURS l'année civile en cours ({today_casablanca().year}), même si le ticket affiche une autre année.
- description : libellé court en français (ex. Gazoil, Cursor, Vol Casa-Paris). Pas le nom fiscal long.
- categorie : EXACTEMENT une valeur parmi : {list(CATEGORIES)}
  Facture photo (essence, resto, SaaS, voyage, téléphone) → plutôt {list(DRIVE_FOLDER_BY_CATEGORY.keys())}.
  Salaire / loyer / charges : seulement si le document correspond vraiment.
- moyen_paiement : EXACTEMENT une valeur parmi {list(MOYENS_PAIEMENT)}. CB Perso seulement si c'est clairement perso. Sinon CB Societe.
- montant : nombre TTC en DH (point décimal JSON, pas de devise)
- confidence : 0 à 1
- uncertain_fields : liste des champs douteux

Si plusieurs montants, prends le total TTC.
"""


def _parse_model_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("JSON Gemini invalide")
    return data


def _normalize_extraction(data: dict[str, Any]) -> dict[str, Any]:
    parsed_date = parse_date(str(data.get("date") or ""), current_year=True)
    montant = parse_montant(data.get("montant"))
    uncertain = data.get("uncertain_fields") or []
    if not isinstance(uncertain, list):
        uncertain = []
    return {
        "date": parsed_date.strftime("%d/%m/%Y") if parsed_date else None,
        "description": str(data.get("description") or "").strip(),
        "categorie": normalize_categorie(data.get("categorie")),
        "moyen_paiement": normalize_moyen(data.get("moyen_paiement")) or "CB Societe",
        "montant": montant,
        "remboursement": "RAS",
        "confidence": float(data.get("confidence") or 0),
        "uncertain_fields": [str(x) for x in uncertain],
        "has_file": True,
    }
