"""Connexion Google perso (une fois) : python -m app.google_login"""

from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from app.google_auth import SCOPES, credentials, oauth_client_path, token_path


def main() -> int:
    client = oauth_client_path()
    if not client.is_file():
        print(
            "Fichier OAuth introuvable : "
            f"{client}\n"
            "Dans Google Cloud Console → Identifiants → Créer → ID client OAuth\n"
            "→ Application de bureau. Télécharge le JSON et place-le sous oauth-client.json."
        )
        return 1
    print("Une page Google va s'ouvrir. Connecte-toi et clique Autoriser.")
    flow = InstalledAppFlow.from_client_secrets_file(str(client), list(SCOPES))
    creds = flow.run_local_server(port=0, prompt="consent", open_browser=True)
    dest = token_path()
    dest.write_text(creds.to_json(), encoding="utf-8")
    credentials.cache_clear()
    print(f"Connecté. Jeton enregistré dans {dest}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
