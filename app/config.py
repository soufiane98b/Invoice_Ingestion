"""Listes métier alignées sur la feuille ApexData (colonnes A–I uniquement)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


# Libellés colonne E (ApexData) — liste fermée.
CATEGORIES: tuple[str, ...] = (
    "Voyage Perso",
    "Assurance Iphone",
    "Gazoil",
    "Outils informatique",
    "Entretien Voiture",
    "Consomable Bureau",
    "Internet",
    "Repas Pro",
    "Syndic Loyer",
    "Comptable",
    "Loyer",
    "Retenue Source Loyer",
    "Salaire Souf",
    "Charges Souf",
    "Salaire Nadia",
    "Charges Nadia",
    "taxe service commune",
)

# Dossiers Drive existants (noms exacts) pour les factures avec fichier.
DRIVE_FOLDER_BY_CATEGORY: dict[str, str] = {
    "Voyage Perso": "Voyage affaire",
    "Assurance Iphone": "Assurance_Portable",
    "Gazoil": "Gazoil",
    "Outils informatique": "Outils_informatique",
    "Entretien Voiture": "Voiture",
    "Consomable Bureau": "Consomable_bureau",
    "Internet": "Internet",
    "Repas Pro": "Repas_pro",
}

DRIVE_FILE_LINK = "https://drive.google.com/file/d/{file_id}/view?usp=drive_link"

MOYENS_PAIEMENT: tuple[str, ...] = (
    "CB Perso",
    "CB Societe",
)

REMBOURSEMENTS: tuple[str, ...] = ("RAS",)

MOIS_FR: tuple[str, ...] = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

# Feuille ApexData existante
DEFAULT_SPREADSHEET_ID = "1kr2GXsZsv8NxdydHc97kK_ELBGc2QImBLT-5ZVmprb4"
DEFAULT_SHEET_GID = 1923965794


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    google_service_account_json: str = ""
    google_oauth_client_json: str = "./oauth-client.json"
    google_token_json: str = "./token.json"
    spreadsheet_id: str = DEFAULT_SPREADSHEET_ID
    sheet_gid: int = DEFAULT_SHEET_GID
    drive_folder_id: str = ""

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = "change-me-long-random"
    whatsapp_app_secret: str = ""
    allowed_whatsapp_number: str = ""

    app_public_url: str = ""
    internal_token: str = "change-me-internal"
    log_level: str = "INFO"
    port: int = 8080


def get_settings() -> Settings:
    return Settings()
