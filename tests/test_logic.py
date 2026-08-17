from app.config import DRIVE_FILE_LINK, DRIVE_FOLDER_BY_CATEGORY
from app.dialogue import apply_corrections, is_cancel, is_no_invoice, is_ok, parse_corrections
from app.extract import _normalize_extraction, empty_draft
from app.dialogue import apply_corrections, is_cancel, is_no_invoice, is_ok, parse_corrections
from app.formatting import folder_mois, format_montant, invoice_filename, parse_date, parse_montant, slugify, unique_filename
from app.normalize import drive_folder_for, normalize_categorie, normalize_moyen, normalize_remboursement


def test_montant_french():
    assert format_montant(745.2) == "745,2"
    assert format_montant(815) == "815"
    assert parse_montant("745,2") == 745.2
    assert parse_montant("1 188 DH") == 1188


def test_date_and_filename():
    d = parse_date("16/05/2026")
    assert d is not None
    assert d.year == 2026 and d.month == 5 and d.day == 16
    name = invoice_filename(d, "Gazoil", 815, "jpg")
    assert name.startswith("2026-05-16_gazoil_815")
    assert folder_mois(d) == "05-2026"
    assert unique_filename("2026-05-16_gazoil_815.jpg", set()) == "2026-05-16_gazoil_815.jpg"
    assert unique_filename(
        "2026-05-16_gazoil_815.jpg",
        {"2026-05-16_gazoil_815.jpg"},
    ) == "2026-05-16_gazoil_815_2.jpg"
    forced = parse_date("20/07/2024", current_year=True)
    assert forced is not None
    assert forced.month == 7 and forced.day == 20
    from app.formatting import today_casablanca

    assert forced.year == today_casablanca().year


def test_slugify():
    assert slugify("Vol Casa-Paris") == "vol_casa_paris"


def test_normalize_lists():
    assert normalize_categorie("gazoil") == "Gazoil"
    assert normalize_categorie("Repas Pro") == "Repas Pro"
    assert normalize_categorie("assurance portable") == "Assurance Iphone"
    assert normalize_categorie("voyage affaire") == "Voyage Perso"
    assert normalize_categorie("voiture") == "Entretien Voiture"
    assert normalize_categorie("Matériel informatique") is None
    assert normalize_moyen("cb societe") == "CB Societe"
    assert normalize_moyen("CB Perso") == "CB Perso"
    assert normalize_moyen("virement societe") is None
    assert normalize_remboursement("papa") == "RAS"
    assert normalize_remboursement(None) == "RAS"
    draft = _normalize_extraction({"moyen_paiement": None, "montant": 10, "categorie": "Gazoil"})
    assert draft["moyen_paiement"] == "CB Societe"
    assert empty_draft("16/05/2026")["moyen_paiement"] == "CB Societe"


def test_drive_folders_and_link():
    assert drive_folder_for("Gazoil") == "Gazoil"
    assert drive_folder_for("Repas Pro") == "Repas_pro"
    assert drive_folder_for("Assurance Iphone") == "Assurance_Portable"
    assert drive_folder_for("Voyage Perso") == "Voyage affaire"
    assert drive_folder_for("Entretien Voiture") == "Voiture"
    assert drive_folder_for("Salaire Souf") is None
    assert set(DRIVE_FOLDER_BY_CATEGORY.values()) == {
        "Voyage affaire",
        "Assurance_Portable",
        "Gazoil",
        "Outils_informatique",
        "Voiture",
        "Consomable_bureau",
        "Internet",
        "Repas_pro",
    }
    file_id = "1j1rHs77gmWmHObLG9MFkjkATlWJcaw6S"
    assert DRIVE_FILE_LINK.format(file_id=file_id) == (
        "https://drive.google.com/file/d/1j1rHs77gmWmHObLG9MFkjkATlWJcaw6S/view?usp=drive_link"
    )


def test_corrections():
    parsed = parse_corrections("montant=800 categorie=Repas Pro moyen=CB Perso")
    assert parsed["montant"] == "800"
    assert parsed["categorie"] == "Repas Pro"
    assert parsed["moyen_paiement"] == "CB Perso"
    draft = {
        "date": "16/05/2026",
        "description": "x",
        "categorie": "Gazoil",
        "moyen_paiement": "CB Societe",
        "montant": 815,
        "remboursement": "RAS",
        "uncertain_fields": ["montant"],
    }
    updated, found = apply_corrections(draft, "montant=800")
    assert found
    assert updated["montant"] == 800.0
    assert "montant" not in updated["uncertain_fields"]


def test_commands():
    assert is_ok("OK")
    assert is_ok("oui")
    assert is_cancel("ANNULER")
    assert is_no_invoice("pas de facture")
    assert is_no_invoice("pas de facture montant=400")
