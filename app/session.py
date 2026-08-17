from __future__ import annotations

import logging
import threading
from typing import Any

from app.config import get_settings
from app.drive_store import read_state_file, write_state_file

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_memory: dict[str, Any] = {
    "draft": None,
    "media_b64": None,
    "media_mime": None,
    "processed_ids": [],
}


def load_state() -> dict[str, Any]:
    settings = get_settings()
    with _lock:
        if _memory.get("draft") is not None or _memory.get("processed_ids"):
            return dict(_memory)
        if settings.drive_folder_id:
            try:
                stored = read_state_file()
                if stored:
                    _memory.update(
                        {
                            "draft": stored.get("draft"),
                            "media_b64": stored.get("media_b64"),
                            "media_mime": stored.get("media_mime"),
                            "processed_ids": stored.get("processed_ids") or [],
                        }
                    )
            except Exception:
                logger.exception("Lecture état Drive impossible, mémoire vide")
        return dict(_memory)


def save_state(
    draft: dict | None = None,
    media_b64: str | None = None,
    media_mime: str | None = None,
    clear_media: bool = False,
    processed_id: str | None = None,
) -> None:
    with _lock:
        if draft is not None:
            _memory["draft"] = draft
        if clear_media:
            _memory["media_b64"] = None
            _memory["media_mime"] = None
        elif media_b64 is not None:
            _memory["media_b64"] = media_b64
            _memory["media_mime"] = media_mime
        if processed_id:
            ids = list(_memory.get("processed_ids") or [])
            if processed_id not in ids:
                ids.append(processed_id)
            _memory["processed_ids"] = ids[-400:]
        _persist()


def clear_draft() -> None:
    with _lock:
        _memory["draft"] = None
        _memory["media_b64"] = None
        _memory["media_mime"] = None
        _persist()


def is_processed(message_id: str) -> bool:
    state = load_state()
    return message_id in (state.get("processed_ids") or [])


def mark_processed(message_id: str) -> None:
    save_state(processed_id=message_id)


def _persist() -> None:
    settings = get_settings()
    if not settings.drive_folder_id:
        return
    try:
        write_state_file(
            {
                "draft": _memory.get("draft"),
                "media_b64": _memory.get("media_b64"),
                "media_mime": _memory.get("media_mime"),
                "processed_ids": _memory.get("processed_ids") or [],
            }
        )
    except Exception:
        logger.exception("Écriture état Drive impossible")
