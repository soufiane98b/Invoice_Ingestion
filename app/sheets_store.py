from __future__ import annotations

import logging
from datetime import date

from app.config import get_settings
from app.formatting import format_date
from app.google_auth import sheets_service

logger = logging.getLogger(__name__)

# Colonnes A–I uniquement. Ne jamais écrire à partir de J (budget).
RANGE_A = "A:A"
WRITE_COLS = "A{row}:I{row}"


def resolve_sheet_title() -> str:
    return _sheet_props()["title"]


def resolve_sheet_id() -> int:
    return int(_sheet_props()["sheetId"])


def _sheet_props() -> dict:
    settings = get_settings()
    meta = (
        sheets_service()
        .spreadsheets()
        .get(
            spreadsheetId=settings.spreadsheet_id,
            fields="sheets.properties",
        )
        .execute()
    )
    for sheet in meta.get("sheets") or []:
        props = sheet.get("properties") or {}
        if int(props.get("sheetId", -1)) == int(settings.sheet_gid):
            return props
    raise RuntimeError(f"Onglet gid={settings.sheet_gid} introuvable dans la feuille.")


def spreadsheet_locale() -> str:
    settings = get_settings()
    meta = (
        sheets_service()
        .spreadsheets()
        .get(spreadsheetId=settings.spreadsheet_id, fields="properties.locale")
        .execute()
    )
    return (meta.get("properties") or {}).get("locale") or "en_US"


def next_empty_row(sheet_title: str) -> int:
    settings = get_settings()
    quoted = _quote_sheet(sheet_title)
    result = (
        sheets_service()
        .spreadsheets()
        .values()
        .get(spreadsheetId=settings.spreadsheet_id, range=f"{quoted}!{RANGE_A}")
        .execute()
    )
    values = result.get("values") or []
    last = 0
    for index, row in enumerate(values, start=1):
        if row and str(row[0]).strip():
            last = index
    return max(last + 1, 2)


def append_invoice_row(
    invoice_date: date,
    description: str,
    categorie: str,
    moyen: str,
    montant: float | None,
    remboursement: str,
    file_url: str | None,
) -> int:
    """Écrit une ligne sur A–I dans le tableau. Retourne le numéro de ligne."""
    settings = get_settings()
    title = resolve_sheet_title()
    sheet_id = resolve_sheet_id()
    row_number = next_empty_row(title)
    _expand_expense_table(sheet_id, row_number)
    _write_invoice_row(
        title=title,
        row_number=row_number,
        invoice_date=invoice_date,
        description=description,
        categorie=categorie,
        moyen=moyen,
        montant=montant,
        remboursement=remboursement,
        file_url=file_url,
    )
    logger.info("Ligne Sheets %s écrite", row_number)
    return row_number


def _write_invoice_row(
    *,
    title: str,
    row_number: int,
    invoice_date: date,
    description: str,
    categorie: str,
    moyen: str,
    montant: float | None,
    remboursement: str,
    file_url: str | None,
) -> None:
    settings = get_settings()
    locale = spreadsheet_locale()
    sep = ";" if locale.lower().startswith("fr") else ","
    if file_url:
        lien = f'=HYPERLINK("{file_url}"{sep}"Voir facture")'
    else:
        lien = "Pas de facture"
    values = [
        [
            format_date(invoice_date),
            f"=YEAR(A{row_number})",
            f'=TEXT(A{row_number}{sep}"mmmm yyyy")',
            description,
            categorie,
            moyen,
            montant if montant is not None else "",
            lien,
            remboursement or "RAS",
        ]
    ]
    quoted = _quote_sheet(title)
    target = f"{quoted}!{WRITE_COLS.format(row=row_number)}"
    sheets_service().spreadsheets().values().update(
        spreadsheetId=settings.spreadsheet_id,
        range=target,
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def _expand_expense_table(sheet_id: int, row_number: int) -> None:
    """Étend le tableau Google (puces, bandes) jusqu'à la ligne écrite."""
    settings = get_settings()
    meta = (
        sheets_service()
        .spreadsheets()
        .get(
            spreadsheetId=settings.spreadsheet_id,
            fields="sheets(properties.sheetId,tables)",
        )
        .execute()
    )
    table = None
    for sheet in meta.get("sheets") or []:
        if int((sheet.get("properties") or {}).get("sheetId", -1)) != int(sheet_id):
            continue
        for candidate in sheet.get("tables") or []:
            rng = candidate.get("range") or {}
            if int(rng.get("startColumnIndex", 0)) == 0 and int(rng.get("endColumnIndex", 0)) >= 9:
                table = candidate
                break
    if not table:
        return
    rng = table.get("range") or {}
    end_row = int(rng.get("endRowIndex") or 0)
    if row_number <= end_row:
        return
    sheets_service().spreadsheets().batchUpdate(
        spreadsheetId=settings.spreadsheet_id,
        body={
            "requests": [
                {
                    "updateTable": {
                        "table": {
                            "tableId": table["tableId"],
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": int(rng.get("startRowIndex") or 0),
                                "endRowIndex": row_number,
                                "startColumnIndex": int(rng.get("startColumnIndex") or 0),
                                "endColumnIndex": int(rng.get("endColumnIndex") or 9),
                            },
                        },
                        "fields": "range",
                    }
                }
            ]
        },
    ).execute()


def _quote_sheet(title: str) -> str:
    escaped = title.replace("'", "''")
    return f"'{escaped}'"
