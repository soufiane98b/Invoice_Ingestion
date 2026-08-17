from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)

SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
)


def _as_path(raw: str) -> Path:
    return Path(raw).expanduser()


def token_path() -> Path:
    settings = get_settings()
    raw = (settings.google_token_json or "./token.json").strip()
    if raw.startswith("{"):
        return Path("/tmp/google-token.json")
    return _as_path(raw)


def oauth_client_path() -> Path:
    settings = get_settings()
    raw = (settings.google_oauth_client_json or "./oauth-client.json").strip()
    if raw.startswith("{"):
        return Path("/tmp/oauth-client.json")
    return _as_path(raw)


def _service_account_info() -> dict:
    settings = get_settings()
    raw = settings.google_service_account_json.strip()
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON manquant. Colle le JSON du compte de service "
            "ou le chemin vers le fichier (voir .env.example)."
        )
    if raw.startswith("{"):
        return json.loads(raw)
    path = _as_path(raw)
    if not path.is_file():
        raise RuntimeError(f"Fichier compte de service introuvable : {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _token_info() -> tuple[dict, Path | None] | None:
    settings = get_settings()
    raw = (settings.google_token_json or "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        return json.loads(raw), None
    path = _as_path(raw)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8")), path


def _load_user_credentials() -> Credentials | None:
    loaded = _token_info()
    if not loaded:
        return None
    info, path = loaded
    creds = Credentials.from_authorized_user_info(info, list(SCOPES))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if path is not None:
            try:
                path.write_text(creds.to_json(), encoding="utf-8")
            except OSError:
                logger.warning("Impossible d'écrire le jeton Google rafraîchi")
    if not creds.valid:
        return None
    return creds


@lru_cache(maxsize=1)
def credentials():
    user = _load_user_credentials()
    if user:
        return user
    return service_account.Credentials.from_service_account_info(
        _service_account_info(),
        scopes=list(SCOPES),
    )


def using_user_oauth() -> bool:
    creds = credentials()
    return isinstance(creds, Credentials)


def drive_service():
    return build("drive", "v3", credentials=credentials(), cache_discovery=False)


def sheets_service():
    return build("sheets", "v4", credentials=credentials(), cache_discovery=False)
