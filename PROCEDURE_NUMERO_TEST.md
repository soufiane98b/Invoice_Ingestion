# Renouveler le numéro de test WhatsApp

Le numéro de test Meta (`+1 555 …`) expire au bout d’environ 90 jours. Le bot Cloud Run, Gemini et Google ne sont pas en cause. WhatsApp affiche alors *This person is no longer on WhatsApp*. L’ancienne discussion est morte : il faut écrire au **nouveau** numéro.

## Ce que l’API ne fait pas

Non, on ne peut pas tout gérer uniquement avec l’API.

| Étape | Où |
|---|---|
| Réclamer un nouveau numéro de test | Écran Meta, bouton **Claim test number**. Pas d’API publique. |
| Ajouter ton portable et saisir le code SMS | Écran Meta, champ **Recipient**. Pas d’API. |
| Générer un jeton d’envoi | Une fois : utilisateur système **invoice-bot**, expiration **Never**. Ne pas utiliser **Generate token** de la page **Try it out** (il meurt en quelques heures). |
| Abonner l’appli **Factures ApexData** au nouveau compte | API. C’est l’étape qui manquait le 16 nov. 2026. |
| Vérifier que le webhook pointe vers Cloud Run | API (lecture). L’URL elle-même se pose une fois dans Meta. |
| Mettre le nouveau Phone number ID en prod | `.env` puis `./deploy/cloudrun.sh`. |

Ne pas ouvrir **Step 2. Production setup** : ça sert à brancher une vraie SIM, pas le numéro de test.

## 1. Écran Meta (manuel)

App **Factures ApexData** → use case **Connect with customers through WhatsApp** → **Step 1. Try it out**.

1. **Claim test number**.
2. Noter trois valeurs affichées à côté du numéro :
   - le numéro (`+1 555 …`) : c’est celui qu’on écrit sur le téléphone
   - **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - **Messaging account ID** → identifiant du compte (WABA), utilisé seulement pour l’abonnement API
3. **Recipient** : ajouter le portable en `+212…`, valider le code. Sans ça, Meta n’accepte pas les messages.
4. Ne pas cliquer **Send message** (modèle de démo).
5. Ne pas cliquer **Generate token** sur cette page, et ne pas remplacer `WHATSAPP_TOKEN` à chaque nouveau numéro. Ce bouton donne un jeton de quelques heures. Le 16 nov. 2026 il a cessé de marcher le soir même : les messages arrivaient (`POST /webhook` 200) mais l’envoi répondait `401` / `code 190`.

Le webhook est déjà :

```
https://invoice-bot-n4qs2xf6ca-uc.a.run.app/webhook
```

Jeton de vérification = `WHATSAPP_VERIFY_TOKEN` dans `.env`. Ne pas le changer. S’il faut le reposer : **Customize → Configuration → Verify and save**, puis cocher **messages**. Ce clic n’envoie rien sur WhatsApp : Meta appelle juste l’URL. Succès = la page reste enregistrée. Échec = erreur rouge sur le jeton.

## Jeton d’envoi (une fois, pas à chaque numéro)

`WHATSAPP_TOKEN` doit être un jeton d’utilisateur système, sans date de fin. Celui en place depuis le 20 nov. 2026 est de type `SYSTEM_USER`, appli **Factures ApexData**, `expires_at` = 0.

Le refaire seulement s’il est révoqué ou si l’envoi renvoie `401` / `code 190`.

1. [business.facebook.com/settings](https://business.facebook.com/settings) → **Users** → **System users**.
2. **invoice-bot** (Admin). S’il n’existe pas : **Add**, rôle Admin.
3. Assets : appli **Factures ApexData** en **Full access**, et le compte WhatsApp du numéro de test (**+1 555 …**) en contrôle total. **Assign people** sur le compte WhatsApp, ou **Add assets** depuis la fiche de l’utilisateur.
4. **Generate token** → appli **Factures ApexData** → expiration **Never** → cocher `whatsapp_business_messaging` et `whatsapp_business_management`.
5. Coller le jeton dans `.env` (`WHATSAPP_TOKEN`) puis `./deploy/cloudrun.sh`. Meta ne le réaffiche pas.

Vérifier sans afficher le jeton (`expires_at` doit valoir 0) :

```bash
cd /Users/soufiane.boustique/Invoice_Ingestion
python3 - <<'PY'
import json, urllib.parse, urllib.request
from pathlib import Path
token = next(l.split("=",1)[1].strip() for l in Path(".env").read_text().splitlines() if l.startswith("WHATSAPP_TOKEN="))
q = urllib.parse.urlencode({"input_token": token, "access_token": token})
with urllib.request.urlopen(f"https://graph.facebook.com/debug_token?{q}", timeout=30) as r:
    info = json.loads(r.read().decode())["data"]
print({k: info.get(k) for k in ("is_valid", "type", "expires_at", "scopes")})
PY
```

Il tombe si on clique **Revoke tokens**, ou si on retire l’appli ou le compte WhatsApp de **invoice-bot**. Un nouveau numéro de test est souvent un nouveau compte WhatsApp : réassigner ce compte à **invoice-bot**, sans régénérer le jeton.

## 2. Abonner l’appli (API)

Réclamer un numéro crée un **nouveau compte** WhatsApp. L’abonnement de l’ancien compte (L3aachir) ne suit pas. Meta n’abonne par défaut que son outil de test (`WA DevX Webhook Events`). Les messages n’arrivent alors jamais sur Cloud Run, même si l’URL de callback est bonne.

Remplace `WABA_ID` par le **Messaging account ID** de l’écran (pas le Phone number ID).

```bash
cd /Users/soufiane.boustique/Invoice_Ingestion
set -a && source .env && set +a

# Liste des applis abonnées. Factures ApexData (1084650210791876) doit y être.
curl -s "https://graph.facebook.com/v21.0/${WABA_ID}/subscribed_apps" \
  -H "Authorization: Bearer ${WHATSAPP_TOKEN}"

# Abonne Factures ApexData. Réponse attendue : {"success":true}
curl -s -X POST "https://graph.facebook.com/v21.0/${WABA_ID}/subscribed_apps" \
  -H "Authorization: Bearer ${WHATSAPP_TOKEN}"
```

Exemple du 16 nov. 2026, à ne pas réutiliser tel quel après un nouveau claim : WABA `1472117121514533`, Phone number ID `1410928035443109`, numéro `+1 555 141-4117`.

Vérifier que le numéro envoie bien vers Cloud Run :

```bash
curl -s "https://graph.facebook.com/v21.0/${WHATSAPP_PHONE_NUMBER_ID}?fields=display_phone_number,webhook_configuration" \
  -H "Authorization: Bearer ${WHATSAPP_TOKEN}"
```

`webhook_configuration.application` doit valoir `https://invoice-bot-n4qs2xf6ca-uc.a.run.app/webhook`.

## 3. Mettre Cloud Run à jour

Dans `.env`, une seule ligne change en temps normal :

```
WHATSAPP_PHONE_NUMBER_ID=<Phone number ID du nouvel écran>
```

Ne pas y mettre le Messaging account ID. Puis :

```bash
./deploy/cloudrun.sh
```

`APP_PUBLIC_URL` reste vide dans `.env` : le script le pose sur Cloud Run.

## 4. Tester

Nouvelle discussion WhatsApp avec le `+1 555 …` affiché. Envoyer `hi`. Réponse attendue du bot (photo, ou le texte d’aide).

Si silence, les logs ne doivent montrer aucun `POST /webhook` :

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="invoice-bot" AND logName:"requests"' \
  --project=maximal-coast-505720-t9 --limit=10 \
  --format='value(timestamp,httpRequest.requestMethod,httpRequest.status,httpRequest.requestUrl)'
```

- Aucun `POST /webhook` : l’abonnement WABA ou le destinataire `+212` manque. Refaire l’étape 2.
- `POST /webhook` en 200, puis `WhatsApp send failed 401` et `code 190` : le jeton d’envoi est mort. Refaire la section **Jeton d’envoi**. Ne pas prendre celui de **Try it out**.
- `POST /webhook` en 200 et pas de bulle, sans 401 : le Phone number ID ne correspond pas au numéro.
- `GET /webhook` en 403 sans `hub.challenge` : quelqu’un a ouvert l’URL dans le navigateur. Ce n’est pas Meta.

## À refaire dans ~90 jours

1. Claim test number + noter Phone number ID et Messaging account ID.
2. Recipient `+212` + code.
3. Réassigner ce compte WhatsApp à **invoice-bot** si c’est un nouveau compte. Garder le même `WHATSAPP_TOKEN`.
4. `POST /{WABA_ID}/subscribed_apps`.
5. `WHATSAPP_PHONE_NUMBER_ID` + `./deploy/cloudrun.sh`.
6. Nouvelle discussion avec le nouveau `+1 555`.
