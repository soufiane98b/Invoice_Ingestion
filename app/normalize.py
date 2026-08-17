from __future__ import annotations

from app.config import CATEGORIES, DRIVE_FOLDER_BY_CATEGORY, MOYENS_PAIEMENT


def _norm(value: str) -> str:
    return " ".join((value or "").casefold().replace("é", "e").replace("è", "e").split())


def closest_choice(value: str | None, choices: tuple[str, ...], default: str | None = None) -> str | None:
    if not value:
        return default
    raw = value.strip()
    if raw in choices:
        return raw
    needle = _norm(raw)
    for choice in choices:
        if _norm(choice) == needle:
            return choice
    for choice in choices:
        if needle in _norm(choice) or _norm(choice) in needle:
            return choice
    return default


def normalize_categorie(value: str | None) -> str | None:
    aliases = {
        "voyage perso": "Voyage Perso",
        "voyage affaire": "Voyage Perso",
        "voyage d affaire": "Voyage Perso",
        "voyage d'affaire": "Voyage Perso",
        "assurance iphone": "Assurance Iphone",
        "assurance portable": "Assurance Iphone",
        "assurance_portable": "Assurance Iphone",
        "gazoil": "Gazoil",
        "gasoil": "Gazoil",
        "essence": "Gazoil",
        "outils informatique": "Outils informatique",
        "outils_informatique": "Outils informatique",
        "entretien voiture": "Entretien Voiture",
        "voiture": "Entretien Voiture",
        "consomable bureau": "Consomable Bureau",
        "consomable_bureau": "Consomable Bureau",
        "consommable bureau": "Consomable Bureau",
        "internet": "Internet",
        "repas pro": "Repas Pro",
        "repas_pro": "Repas Pro",
        "syndic loyer": "Syndic Loyer",
        "comptable": "Comptable",
        "loyer": "Loyer",
        "retenue source loyer": "Retenue Source Loyer",
        "salaire souf": "Salaire Souf",
        "charges souf": "Charges Souf",
        "salaire nadia": "Salaire Nadia",
        "charges nadia": "Charges Nadia",
        "taxe service commune": "taxe service commune",
    }
    if value:
        mapped = aliases.get(_norm(value.replace("_", " ")))
        if mapped:
            return mapped
        underscored = aliases.get(_norm(value))
        if underscored:
            return underscored
    return closest_choice(value, CATEGORIES)


def drive_folder_for(categorie: str | None) -> str | None:
    if not categorie:
        return None
    return DRIVE_FOLDER_BY_CATEGORY.get(categorie)


def normalize_moyen(value: str | None) -> str | None:
    aliases = {
        "cb perso": "CB Perso",
        "carte perso": "CB Perso",
        "perso": "CB Perso",
        "cb societe": "CB Societe",
        "cb société": "CB Societe",
        "carte societe": "CB Societe",
        "societe": "CB Societe",
        "société": "CB Societe",
    }
    if value:
        mapped = aliases.get(_norm(value))
        if mapped:
            return mapped
    return closest_choice(value, MOYENS_PAIEMENT)


def normalize_remboursement(_value: str | None = None) -> str:
    return "RAS"
