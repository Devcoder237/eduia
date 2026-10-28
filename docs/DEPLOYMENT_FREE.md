# Déploiement 100 % gratuit — pas à pas

Durée : ≈ 45 min. Aucune carte bancaire. Prérequis : un compte GitHub, un dépôt **public** contenant ce projet.

> Remplacez les noms entre `<…>` par les vôtres. Ne collez jamais un secret dans le code ni dans un ticket.

## 1. Publier le code sur GitHub
```bash
git init && git add . && git commit -m "Initial commit"
git branch -M main && git remote add origin https://github.com/<vous>/eduia.git && git push -u origin main
```
Vérifiez que `.env` n'apparaît pas dans `git status`. Dépôt **public** = minutes GitHub Actions illimitées.

## 2. Créer la base — Neon (https://neon.tech)
1. Créez un projet (région la plus proche, ex. Frankfurt).
2. Dans *Connection details*, copiez **deux** URL :
   - **Pooled** (host contenant `-pooler`) → `DATABASE_URL`
   - **Direct** (sans `-pooler`) → `MIGRATION_DATABASE_URL`
3. Collez les URL telles quelles (`postgresql://…?sslmode=require`) : l'application les convertit pour asyncpg.

## 3. Générer les secrets
```bash
python backend/scripts/generate_secret.py   # → SECRET_KEY
```
Clé OpenAI : https://platform.openai.com/api-keys (facultative : sans clé, mode dégradé).

## 4. Déployer l'API — Render (https://render.com)
1. *New → Web Service* → connectez le dépôt.
2. *Language* : **Docker** · *Root Directory* : `backend` · *Instance Type* : **Free**.
3. Variables d'environnement :

| Variable | Valeur |
|---|---|
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | sortie de l'étape 3 |
| `DATABASE_URL` | URL pooler Neon |
| `MIGRATION_DATABASE_URL` | URL directe Neon |
| `OPENAI_API_KEY` | votre clé |
| `CORS_ORIGINS` | URL du front (étape 5), sans slash final |
| `SENTRY_DSN` | facultatif (étape 8) |

4. *Health Check Path* : `/health`. Les migrations Alembic s'exécutent au démarrage du conteneur.
5. Notez l'URL : `https://<service>.onrender.com`. Test : `curl https://<service>.onrender.com/health`.

*Alternative Koyeb* : même Dockerfile (dossier `backend`), instance gratuite, mêmes variables, port `8000`.

## 5. Déployer le front — Cloudflare Pages (https://pages.cloudflare.com)
1. *Create → Pages → Connect to Git* → le dépôt.
2. *Root directory* `frontend` · *Build command* `npm install && npm run build` · *Output* `dist`.
3. Variable de build : `VITE_API_URL=https://<service>.onrender.com` (origine seule, sans `/api`).
4. Déployez → vous obtenez `https://<projet>.pages.dev`. Retournez à l'étape 4 et mettez cette URL dans `CORS_ORIGINS`, puis redéployez l'API.

*Alternative Vercel* : même réglage (framework Vite) ; les fichiers `_headers` / `_redirects` sont propres à Cloudflare — sur Vercel, ajoutez un `vercel.json` avec une réécriture `/(.*)` → `/index.html`.

*Facultatif* : `VITE_CONTACT_EMAIL` (adresse affichée dans les conditions d'utilisation).

> ⚖️ Les textes de `LegalPage` sont un **modèle** : faites-les valider par un juriste (loi camerounaise de protection des données personnelles) avant d'ouvrir le service à des mineurs.

## 6. Créer le premier administrateur
Le *Shell* de Render est payant : on crée le compte **depuis votre ordinateur**, en pointant vers Neon (une seule fois).
```bash
cd backend
pip install -r requirements.txt
# Linux/macOS :
DATABASE_URL="<URL directe Neon>" SECRET_KEY="<la même clé que sur Render>" python -m scripts.create_admin
# Windows PowerShell :
$env:DATABASE_URL="<URL directe Neon>"; $env:SECRET_KEY="<la même clé>"; python -m scripts.create_admin
```
Le script demande l'e-mail, le nom d'utilisateur et le mot de passe (non affiché). Ajoutez `--teacher` pour un compte enseignant. L'API doit avoir démarré au moins une fois (étape 4) pour que les tables existent. `seed_db.py` est réservé au développement.

## 6 bis. E-mails « mot de passe oublié » (SMTP gratuit)

Sans SMTP, le lien de réinitialisation n'est **pas envoyé** (en production, le journal indique `smtp_not_configured`). Il faut donc un service d'envoi gratuit :

1. Crée un compte sur **Brevo** (https://www.brevo.com, offre gratuite ~300 e-mails/jour) puis génère une clé SMTP (SMTP & API → SMTP).
2. Valide l'adresse d'expéditeur dans Brevo (obligatoire, sinon les e-mails sont refusés).
3. Dans les variables d'environnement Render, ajoute :
   - `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`
   - `SMTP_USER` et `SMTP_PASSWORD` (identifiants SMTP Brevo, jamais dans le code)
   - `SMTP_FROM=EduIA <adresse-validee@exemple.com>`
   - `FRONTEND_URL=https://ton-site.pages.dev` (adresse publique du front, **sans** `/` final : elle sert à construire le lien)
4. Redéploie, puis teste « Mot de passe oublié ? » avec ton propre compte.

Le lien est valable 30 minutes (`RESET_TOKEN_EXPIRE_MINUTES`), ne sert qu'une fois, et déconnecte tous les appareils. La réponse de l'API est identique que l'e-mail existe ou non (pas de fuite sur les comptes).

## 7. Éviter l'endormissement — UptimeRobot (https://uptimerobot.com)
*Add monitor* → HTTP(s) → URL `https://<service>.onrender.com/health` → intervalle **5 min** (minimum gratuit ; 14 min suffit pour Render). En secours, dans GitHub : *Settings → Secrets and variables → Actions → Variables* → `API_URL` = URL de l'API ; `keepalive.yml` pingue alors toutes les 14 min.

## 8. Sentry (facultatif) — https://sentry.io
Créez un projet *Python/FastAPI* → copiez le DSN dans `SENTRY_DSN` (Render). Pour le front : projet *Browser JavaScript* → `VITE_SENTRY_DSN` (Cloudflare Pages).

## 9. Sauvegardes — Cloudflare R2 (facultatif mais recommandé)
1. R2 → créez un bucket `eduia-backups`, puis un jeton API (lecture/écriture sur ce bucket).
2. GitHub → *Settings → Secrets → Actions* : `DATABASE_URL_DIRECT`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`.
3. `backup.yml` s'exécute chaque jour ; lancez-le une fois à la main (*Actions → Run workflow*) pour valider.

## 10. Vérifier
- `https://<service>.onrender.com/health` → `{"status":"ok",…}` ; `/health/ready` → base joignable.
- Ouvrez le site, créez un compte, posez une question au tuteur.
- *Actions* : CI verte.

## Erreurs fréquentes

| Symptôme | Cause / solution |
|---|---|
| Build front : « VITE_API_URL est manquant » | Variable de build absente (étape 5). |
| Console navigateur : erreur CORS | `CORS_ORIGINS` ne correspond pas exactement à l'URL du front (schéma, pas de `/` final). |
| API ne démarre pas : « SECRET_KEY » | Clé absente, trop courte (< 32) ou valeur d'exemple. |
| « SQLite est interdit en production » | `DATABASE_URL` non définie sur Render. |
| Migration : `prepared statement … already exists` | Alembic doit utiliser l'URL **directe** (`MIGRATION_DATABASE_URL`), pas le pooler. |
| Première requête très lente (≈ 30 s) | Réveil de Render : normal sans UptimeRobot ; le front affiche l'écran d'attente. |
| Connexion lente après inactivité | Neon se réveille (≈ 1–2 s). |
| 401 en boucle | `SECRET_KEY` changée : les anciennes sessions sont invalidées, reconnectez-vous. |

## Limites du gratuit
- **Démarrage à froid** Render : ≈ 30 s après 15 min sans trafic (atténué par UptimeRobot).
- **≈ 750 h/mois** d'instance gratuite Render : suffisant pour un seul service 24/7 (31 j = 744 h).
- **512 Mo de RAM** : un seul worker, pool de connexions réduit, pas d'OCR ni de traitement lourd.
- **Disque éphémère** : rien d'important n'est écrit sur disque ; tout est dans Neon.
- **Neon Free** : stockage et heures de calcul limités ; mise en veille après inactivité.
- **Limiteur de débit en mémoire** : réinitialisé à chaque redémarrage de l'API.
- **Quota LLM** : l'API OpenAI est payante à l'usage ; `DAILY_LLM_QUOTA` borne la dépense par utilisateur.
- Les offres gratuites peuvent changer : vérifiez les conditions de chaque fournisseur.
