"""Test local : python -m app.cli chemin/vers/facture.jpg

Sans --ecrire : extraction seulement (rien n'est écrit dans Drive / Sheets).
Avec --ecrire : dépose le fichier et ajoute une ligne ApexData.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from pathlib import Path

from app.extract import extract_invoice
from app.formatting import format_montant
from app.image_util import compress_image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extraction locale d'une facture. N'écrit rien sauf avec --ecrire."
    )
    parser.add_argument("image", nargs="+", help="Photo ou PDF de facture")
    parser.add_argument(
        "--ecrire",
        action="store_true",
        help="Dépose le fichier dans Drive et ajoute une ligne dans la feuille ApexData",
    )
    args = parser.parse_args(argv)
    path = Path(" ".join(args.image))
    if not path.is_file():
        print(f"Fichier introuvable : {path}", file=sys.stderr)
        return 1
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = path.read_bytes()
    if mime.startswith("image/"):
        data, mime = compress_image(data, mime)
    draft = extract_invoice(data, mime)
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    if draft.get("montant") is not None:
        print(f"Montant format feuille : {format_montant(draft['montant'])} DH")
    if not args.ecrire:
        print("Aucune écriture Drive/Sheets (ajoute --ecrire pour ingérer).")
        return 0
    if not draft.get("categorie") or draft.get("montant") is None:
        print("Ingestion impossible : catégorie ou montant manquant.", file=sys.stderr)
        return 1
    from app.ingest import ingest

    row, file_url = ingest(draft, data, mime)
    print(f"Ligne Sheets : {row}")
    if file_url:
        print(f"Fichier Drive : {file_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
