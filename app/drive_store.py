from __future__ import annotations

import io
import json
import logging
from datetime import date

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from app.config import DRIVE_FILE_LINK, get_settings
from app.formatting import folder_mois, invoice_filename, unique_filename
from app.google_auth import _service_account_info, drive_service
from app.normalize import drive_folder_for

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
STATE_NAME = "bot-state.json"


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_or_create_folder(name: str, parent_id: str) -> str:
    service = drive_service()
    query = (
        f"name = '{_escape_query(name)}' and '{parent_id}' in parents "
        f"and mimeType = '{FOLDER_MIME}' and trashed = false"
    )
    result = (
        service.files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
        )
        .execute()
    )
    files = result.get("files") or []
    if files:
        return files[0]["id"]
    try:
        created = (
            service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": FOLDER_MIME,
                    "parents": [parent_id],
                },
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise _drive_parent_error(parent_id, exc) from exc
    return created["id"]


def _filenames_in_folder(parent_id: str) -> set[str]:
    result = (
        drive_service()
        .files()
        .list(
            q=f"'{parent_id}' in parents and trashed = false",
            spaces="drive",
            fields="files(name)",
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="allDrives",
        )
        .execute()
    )
    return {f["name"] for f in result.get("files") or [] if f.get("name")}


def _drive_upload_error(parent_id: str, exc: HttpError) -> RuntimeError:
    body = str(exc)
    if getattr(exc, "status_code", None) == 404:
        return _drive_parent_error(parent_id, exc)
    if "storageQuotaExceeded" in body or "Service Accounts do not have storage quota" in body:
        return RuntimeError(
            "Google refuse d'uploader avec un compte de service (quota Drive = 0). "
            "Connecte le Gmail qui possède le dossier Factures : python -m app.google_login"
        )
    return RuntimeError(str(exc))


def _drive_parent_error(parent_id: str, exc: HttpError) -> RuntimeError:
    if getattr(exc, "status_code", None) != 404:
        return RuntimeError(str(exc))
    email = _service_account_info().get("client_email", "compte de service")
    return RuntimeError(
        f"Dossier Drive introuvable pour {email} (id={parent_id}). "
        "Ouvre le dossier Factures → Partager → Éditeur pour cet email, "
        "puis mets l'ID du dossier Factures (celui de l'URL) dans DRIVE_FOLDER_ID."
    )


def upload_invoice(
    media: bytes,
    mime: str,
    invoice_date: date,
    categorie: str,
    description: str,
    montant: float | None,
) -> dict:
    settings = get_settings()
    if not settings.drive_folder_id:
        raise RuntimeError("DRIVE_FOLDER_ID manquant. Partage le dossier Factures avec le compte de service.")

    year_id = find_or_create_folder(str(invoice_date.year), settings.drive_folder_id)
    folder_name = drive_folder_for(categorie)
    category_id = find_or_create_folder(folder_name, year_id) if folder_name else year_id
    parent_id = find_or_create_folder(folder_mois(invoice_date), category_id)

    ext = "pdf" if mime == "application/pdf" else "jpg"
    upload_mime = "application/pdf" if ext == "pdf" else "image/jpeg"
    filename = unique_filename(
        invoice_filename(invoice_date, description, montant, ext),
        _filenames_in_folder(parent_id),
    )

    media_body = MediaIoBaseUpload(io.BytesIO(media), mimetype=upload_mime, resumable=False)
    try:
        created = (
            drive_service()
            .files()
            .create(
                body={"name": filename, "parents": [parent_id]},
                media_body=media_body,
                fields="id, name",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise _drive_upload_error(parent_id, exc) from exc
    file_id = created["id"]
    link = DRIVE_FILE_LINK.format(file_id=file_id)
    logger.info("Fichier Drive créé %s", link)
    return {"id": file_id, "name": created.get("name"), "webViewLink": link}


def read_state_file() -> dict:
    file_id = _find_state_file()
    if not file_id:
        return {}
    content = (
        drive_service()
        .files()
        .get_media(fileId=file_id, supportsAllDrives=True)
        .execute()
    )
    try:
        return json.loads(content.decode("utf-8"))
    except Exception:
        return {}


def write_state_file(state: dict) -> None:
    settings = get_settings()
    payload = json.dumps(state, ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(payload), mimetype="application/json", resumable=False)
    file_id = _find_state_file()
    if file_id:
        drive_service().files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
        return
    drive_service().files().create(
        body={"name": STATE_NAME, "parents": [settings.drive_folder_id]},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()


def _find_state_file() -> str | None:
    settings = get_settings()
    if not settings.drive_folder_id:
        return None
    query = (
        f"name = '{STATE_NAME}' and '{settings.drive_folder_id}' in parents and trashed = false"
    )
    result = (
        drive_service()
        .files()
        .list(
            q=query,
            spaces="drive",
            fields="files(id)",
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = result.get("files") or []
    return files[0]["id"] if files else None
