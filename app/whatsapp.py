from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
GRAPH_BASE = "https://graph.facebook.com/v21.0"


def send_text(to: str, body: str) -> None:
    settings = get_settings()
    url = f"{GRAPH_BASE}/{settings.whatsapp_phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=payload, headers=headers)
        if response.status_code >= 300:
            logger.error("WhatsApp send failed %s %s", response.status_code, response.text)
            response.raise_for_status()


def download_media(media_id: str) -> tuple[bytes, str]:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    with httpx.Client(timeout=60) as client:
        meta = client.get(f"{GRAPH_BASE}/{media_id}", headers=headers)
        meta.raise_for_status()
        media_url = meta.json()["url"]
        mime = meta.json().get("mime_type") or "image/jpeg"
        binary = client.get(media_url, headers=headers)
        binary.raise_for_status()
        return binary.content, mime


def parse_incoming(payload: dict) -> list[dict]:
    """Aplati les messages WhatsApp utiles (ignore les accusés de réception)."""
    messages: list[dict] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for msg in value.get("messages") or []:
                parsed = _one_message(msg)
                if parsed:
                    messages.append(parsed)
    return messages


def _one_message(msg: dict) -> dict | None:
    msg_type = msg.get("type")
    base = {
        "id": msg.get("id"),
        "from": msg.get("from"),
        "type": msg_type,
        "text": "",
        "media_id": None,
        "mime": None,
        "filename": None,
    }
    if msg_type == "text":
        base["text"] = (msg.get("text") or {}).get("body") or ""
        return base
    if msg_type == "image":
        image = msg.get("image") or {}
        base["media_id"] = image.get("id")
        base["mime"] = image.get("mime_type") or "image/jpeg"
        base["text"] = image.get("caption") or ""
        return base
    if msg_type == "document":
        doc = msg.get("document") or {}
        mime = doc.get("mime_type") or ""
        if mime not in ("application/pdf", "image/jpeg", "image/png", "image/webp"):
            base["type"] = "unsupported"
            return base
        base["media_id"] = doc.get("id")
        base["mime"] = mime
        base["filename"] = doc.get("filename")
        base["text"] = doc.get("caption") or ""
        return base
    return None
