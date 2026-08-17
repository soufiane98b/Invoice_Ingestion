from __future__ import annotations

import base64
import logging
import threading
from typing import Any

from app.config import get_settings
from app.dialogue import (
    apply_corrections,
    format_recap,
    is_cancel,
    is_no_invoice,
    is_ok,
    missing_required,
    moyens_help,
)
from app.extract import empty_draft, extract_invoice
from app.formatting import digits_only, format_date, today_casablanca
from app.image_util import compress_image
from app.ingest import ingest
from app.session import clear_draft, is_processed, load_state, mark_processed, save_state
from app.whatsapp import download_media, parse_incoming, send_text

logger = logging.getLogger(__name__)
_inflight: set[str] = set()
_inflight_lock = threading.Lock()


def handle_webhook_payload(payload: dict) -> None:
    for message in parse_incoming(payload):
        try:
            _handle_one(message)
        except Exception:
            logger.exception("Erreur message %s", message.get("id"))
            sender = message.get("from")
            if sender:
                try:
                    send_text(sender, "Erreur pendant le traitement. Réessaie ou envoie ANNULER.")
                except Exception:
                    logger.exception("Impossible de notifier l'erreur WhatsApp")


def _handle_one(message: dict) -> None:
    settings = get_settings()
    sender = digits_only(message.get("from") or "")
    allowed = digits_only(settings.allowed_whatsapp_number)
    if allowed and sender != allowed:
        logger.warning("Numéro ignoré %s", sender)
        return

    msg_id = message.get("id") or ""
    if msg_id and is_processed(msg_id):
        logger.info("Message déjà traité %s", msg_id)
        return
    with _inflight_lock:
        if msg_id and msg_id in _inflight:
            logger.info("Message déjà en cours %s", msg_id)
            return
        if msg_id:
            _inflight.add(msg_id)

    try:
        if message.get("type") == "unsupported":
            send_text(sender, "Envoie une photo, un PDF, ou le texte pas de facture.")
            return

        if message.get("media_id"):
            _handle_media(sender, message)
            return

        text = (message.get("text") or "").strip()
        if not text:
            send_text(sender, "Envoie une photo de facture, ou écris pas de facture.")
            return
        _handle_text(sender, text)
    finally:
        if msg_id:
            mark_processed(msg_id)
            with _inflight_lock:
                _inflight.discard(msg_id)


def _handle_media(sender: str, message: dict) -> None:
    send_text(sender, "Photo reçue, je lis la facture…")
    raw, mime = download_media(message["media_id"])
    mime = message.get("mime") or mime or "image/jpeg"
    if mime.startswith("image/"):
        raw, mime = compress_image(raw, mime)
    hint = (message.get("text") or "").strip()
    draft = extract_invoice(raw, mime, user_hint=hint)
    if not draft.get("date"):
        draft["date"] = format_date(today_casablanca())
    draft["remboursement"] = "RAS"
    save_state(
        draft=draft,
        media_b64=base64.b64encode(raw).decode("ascii"),
        media_mime=mime,
    )
    send_text(sender, format_recap(draft, prefix="Je propose :"))


def _handle_text(sender: str, text: str) -> None:
    if is_cancel(text):
        clear_draft()
        send_text(sender, "Brouillon annulé. Envoie une nouvelle photo quand tu veux.")
        return

    if is_no_invoice(text):
        draft = empty_draft(format_date(today_casablanca()))
        draft, _ = apply_corrections(draft, text)
        save_state(draft=draft, clear_media=True)
        send_text(
            sender,
            format_recap(draft, prefix="Pas de fichier. Complète puis OK.")
            + "\n"
            + moyens_help(),
        )
        return

    state = load_state()
    draft = state.get("draft")

    if is_ok(text):
        if not draft:
            send_text(sender, "Aucun brouillon. Envoie d'abord une photo (ou pas de facture).")
            return
        missing = missing_required(draft)
        if missing:
            send_text(
                sender,
                "Il manque : "
                + ", ".join(missing)
                + ".\nCorrige avec categorie=… montant=… moyen=…\n"
                + moyens_help(),
            )
            return
        media, mime = _media_from_state(state)
        try:
            row, url = ingest(draft, media, mime)
        except Exception as exc:
            logger.exception("Ingestion échouée")
            send_text(sender, f"Ingestion échouée : {exc}")
            return
        clear_draft()
        link_txt = f"\n{url}" if url else ""
        send_text(
            sender,
            f"Ingéré : ligne {row} ajoutée dans ApexData (A–I)."
            f"{link_txt}",
        )
        return

    if not draft:
        send_text(
            sender,
            "Envoie une *photo* de facture.\n"
            "Ou *pas de facture* pour une ligne sans fichier (salaire, CCA…).",
        )
        return

    updated, found = apply_corrections(draft, text)
    if found:
        save_state(draft=updated)
        send_text(sender, format_recap(updated, prefix="C'est noté, je propose :"))
        return

    send_text(
        sender,
        "Je n'ai pas compris. Réponds OK, ANNULER, ou une correction du type montant=800.",
    )


def _media_from_state(state: dict[str, Any]) -> tuple[bytes | None, str | None]:
    b64 = state.get("media_b64")
    mime = state.get("media_mime")
    if not b64:
        return None, None
    return base64.b64decode(b64), mime
