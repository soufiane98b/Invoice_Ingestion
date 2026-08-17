from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import MOIS_FR

CASABLANCA = ZoneInfo("Africa/Casablanca")


def today_casablanca() -> date:
    return datetime.now(CASABLANCA).date()


def with_current_year(d: date) -> date:
    """Les factures sont toujours de l'année civile en cours (Casablanca)."""
    year = today_casablanca().year
    try:
        return d.replace(year=year)
    except ValueError:
        return date(year, 2, 28)


def parse_date(value: str | None, *, current_year: bool = False) -> date | None:
    if not value:
        return None
    raw = value.strip()
    parsed: date | None = None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    return with_current_year(parsed) if current_year else parsed


def format_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def format_mois(d: date) -> str:
    return f"{MOIS_FR[d.month]} {d.year}"


def folder_mois(d: date) -> str:
    """Dossier Drive du mois, ex. 07-2026."""
    return f"{d.month:02d}-{d.year}"


def format_montant(value: float | int | str) -> str:
    if isinstance(value, str):
        parsed = parse_montant(value)
        if parsed is None:
            return value.strip()
        value = parsed
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    text = f"{number:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def parse_montant(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = (
        str(value)
        .strip()
        .replace("DH", "")
        .replace("Mad", "")
        .replace("MAD", "")
        .replace(" ", "")
        .replace("\u00a0", "")
    )
    if not raw:
        return None
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def slugify(value: str, max_len: int = 40) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return (slug or "facture")[:max_len]


def invoice_filename(d: date, description: str, montant: float | None, ext: str) -> str:
    amount = format_montant(montant) if montant is not None else "na"
    amount = amount.replace(",", ".")
    return f"{d.isoformat()}_{slugify(description)}_{amount}.{ext.lstrip('.')}"


def unique_filename(name: str, existing: set[str]) -> str:
    taken = {n.casefold() for n in existing}
    if name.casefold() not in taken:
        return name
    if "." in name:
        stem, ext = name.rsplit(".", 1)
        suffix = f".{ext}"
    else:
        stem, suffix = name, ""
    n = 2
    while True:
        candidate = f"{stem}_{n}{suffix}"
        if candidate.casefold() not in taken:
            return candidate
        n += 1


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")
