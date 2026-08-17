from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.config import get_settings
from app.handler import handle_webhook_payload

logger = logging.getLogger("invoice_bot")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Invoice bot prêt")
    yield


app = FastAPI(title="Invoice WhatsApp bot", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    return """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Politique de confidentialité — Factures ApexData</title></head>
<body style="font-family:sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.5">
<h1>Politique de confidentialité</h1>
<p>Bot personnel WhatsApp d’ApexData (Soufiane Boustique). Usage privé, un seul utilisateur.</p>
<h2>Données</h2>
<p>Photos et PDF de factures envoyés sur WhatsApp, plus les champs extraits (date, montant, catégorie, moyen de paiement).</p>
<h2>Usage</h2>
<p>Lecture automatique de la facture, classement dans Google Drive et ajout d’une ligne dans Google Sheets, uniquement après validation par l’utilisateur.</p>
<h2>Prestataires</h2>
<ul>
<li>Meta / WhatsApp (acheminement des messages)</li>
<li>Google Gemini (lecture du document)</li>
<li>Google Drive et Google Sheets (stockage)</li>
</ul>
<p>Pas de revente, pas de publicité, pas de partage à d’autres personnes.</p>
<h2>Contact</h2>
<p>datasoku.boustique@gmail.com</p>
</body></html>
"""


@app.get("/webhook")
def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
):
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Verify token invalide")


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()
    settings = get_settings()
    if settings.whatsapp_app_secret:
        signature = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.whatsapp_app_secret.encode("utf-8"),
            raw,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="signature")
    payload = json.loads(raw or b"{}")
    # Meta veut un 200 en ~5 s. Gemini prend plus longtemps :
    # - en prod, on relance une requête Cloud Run /internal/process (CPU alloué)
    # - en local, tâche de fond uvicorn
    if settings.app_public_url:
        threading.Thread(target=_dispatch_internal, args=(payload,), daemon=True).start()
        await asyncio.sleep(0.4)
    else:
        background_tasks.add_task(_run_handler, payload)
    return {"status": "ok"}


@app.post("/internal/process")
async def internal_process(
    request: Request,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
):
    settings = get_settings()
    if x_internal_token != settings.internal_token:
        raise HTTPException(status_code=401, detail="token")
    payload = await request.json()
    _run_handler(payload)
    return {"status": "processed"}


def _run_handler(payload: dict) -> None:
    try:
        handle_webhook_payload(payload)
    except Exception:
        logger.exception("Handler WhatsApp")


def _dispatch_internal(payload: dict) -> None:
    import httpx

    settings = get_settings()
    url = settings.app_public_url.rstrip("/") + "/internal/process"
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                json=payload,
                headers={"X-Internal-Token": settings.internal_token},
            )
            if response.status_code >= 300:
                logger.error("Dispatch interne %s %s", response.status_code, response.text)
    except Exception:
        logger.exception("Dispatch interne impossible, fallback local")
        _run_handler(payload)
