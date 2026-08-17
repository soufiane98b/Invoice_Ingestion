#!/usr/bin/env bash
# Déploiement Cloud Run (quota gratuit, us-central1, min-instances=0).
# Usage : PROJECT_ID=maximal-coast-505720-t9 ./deploy/cloudrun.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${PROJECT_ID:-maximal-coast-505720-t9}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-invoice-bot}"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "gcloud introuvable. Installe-le :"
  echo "  brew install --cask google-cloud-cli"
  echo "puis :"
  echo "  gcloud auth login"
  echo "  gcloud auth application-default login"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Fichier .env introuvable."
  exit 1
fi
if [[ ! -f token.json ]]; then
  echo "token.json introuvable. Lance d'abord : python -m app.google_login"
  exit 1
fi

ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT

python3 - "$ENV_FILE" "$ROOT" <<'PY'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
root = Path(sys.argv[2])
env: dict[str, str] = {}
for raw in (root / ".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    env[key.strip()] = value.strip().strip("'").strip('"')

def inline_json(path: Path) -> str:
    return json.dumps(json.loads(path.read_text(encoding="utf-8")), separators=(",", ":"))

if (root / "token.json").is_file():
    env["GOOGLE_TOKEN_JSON"] = inline_json(root / "token.json")
if (root / "oauth-client.json").is_file():
    env["GOOGLE_OAUTH_CLIENT_JSON"] = inline_json(root / "oauth-client.json")
if (root / "service-account.json").is_file():
    env["GOOGLE_SERVICE_ACCOUNT_JSON"] = inline_json(root / "service-account.json")

# Rempli après le premier deploy, une fois l'URL connue.
env.pop("APP_PUBLIC_URL", None)

lines = []
for key, value in env.items():
    lines.append(f"{key}: {json.dumps(value)}")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Variables : {len(env)} clés (valeurs masquées)")
PY

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  drive.googleapis.com \
  sheets.googleapis.com

gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 120 \
  --concurrency 5 \
  --min-instances 0 \
  --max-instances 2 \
  --cpu-boost \
  --env-vars-file "$ENV_FILE" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
gcloud run services update "$SERVICE" \
  --region "$REGION" \
  --update-env-vars "APP_PUBLIC_URL=${URL}" \
  --quiet

echo
echo "Service : $URL"
echo "Santé  : $URL/health"
echo "Webhook Meta : $URL/webhook"
echo
echo "Dans Meta → WhatsApp → Configuration :"
echo "  URL de rappel = $URL/webhook"
echo "  Jeton de vérification = la même valeur que WHATSAPP_VERIFY_TOKEN dans .env"
echo "  Abonne messages"
echo
echo "Alerte budget : console.cloud.google.com/billing/budgets?project=$PROJECT_ID"
