from __future__ import annotations

from app.drive_store import upload_invoice
from app.formatting import parse_date, today_casablanca
from app.sheets_store import append_invoice_row


def ingest(
    draft: dict,
    media: bytes | None,
    mime: str | None,
) -> tuple[int, str | None]:
    invoice_date = parse_date(draft.get("date"), current_year=True) or today_casablanca()
    description = (draft.get("description") or draft.get("categorie") or "facture").strip()
    categorie = draft.get("categorie")
    moyen = draft.get("moyen_paiement")
    montant = draft.get("montant")
    remboursement = "RAS"
    if not categorie or not moyen:
        raise ValueError("Catégorie et moyen de paiement sont requis.")

    file_url = None
    if media and mime and mime != "text/plain":
        uploaded = upload_invoice(
            media=media,
            mime=mime,
            invoice_date=invoice_date,
            categorie=categorie,
            description=description,
            montant=montant,
        )
        file_url = uploaded.get("webViewLink")

    row = append_invoice_row(
        invoice_date=invoice_date,
        description=description,
        categorie=categorie,
        moyen=moyen,
        montant=montant,
        remboursement=remboursement,
        file_url=file_url,
    )
    return row, file_url
