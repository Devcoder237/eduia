# EduIA — Tuteur intelligent
> **English summary**: EduIA is an adaptive intelligent tutoring system built for Cameroonian learners. It tracks mastery per concept with Bayesian Knowledge Tracing (with forgetting and spaced repetition), grounds answers with BM25 retrieval (RAG), verifies multiple-choice answer keys, and measures calibration of learners' confidence. See `docs/PEDAGOGIE.md` for the model and its limits.
Tuteur IA pour élèves et étudiants (primaire → université), FR/EN : chat pédagogique en streaming (modes explication et socratique), exercices corrigés, quiz, examens blancs chronométrés côté serveur, plans d'étude, suivi des progrès, espace enseignant.

- **Backend** : FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL (Neon), JWT avec révocation.
- **Frontend** : React 18, Vite, TypeScript strict, i18n FR/EN, thème clair/sombre, PWA, WCAG AA.
- **Coût d'hébergement : 0 €** (voir ci-dessous).

## Démarrage local

```bash
cp .env.example .env            # renseigner SECRET_KEY (make secret) et OPENAI_API_KEY
make up                         # PostgreSQL + API (http://localhost:8000) via Docker
cd frontend && cp .env.example .env && npm install && npm run dev   # http://localhost:5173
```

Sans Docker : `cd backend && pip install -r requirements-dev.txt && cp .env.example .env && alembic upgrade head && uvicorn app.main:app --reload`.

Commandes utiles : `make test`, `make lint`, `make audit`, `make migrate` (`make help`).

## Déploiement 100 % gratuit

| Composant | Service gratuit | Rôle |
|---|---|---|
| API | Render (Docker, plan Free) ou Koyeb | FastAPI, 512 Mo RAM, disque éphémère |
| Base de données | Neon Free (pooler) | PostgreSQL persistant |
| Front | Cloudflare Pages | Site statique + CDN, sous-domaine `*.pages.dev` |
| Sauvegardes | Cloudflare R2 + GitHub Actions | Dump quotidien chiffré par le transport |
| CI | GitHub Actions (dépôt public) | Tests, types, audit, build Docker |
| Erreurs | Sentry Free | Backend (+ front en option) |
| Anti-veille | UptimeRobot (toutes les 14 min) | Ping de `/health` |

Aucune carte bancaire n'est requise. Guide pas à pas : **[docs/DEPLOYMENT_FREE.md](docs/DEPLOYMENT_FREE.md)**.

**Démarrage à froid** : Render Free met l'API en veille après 15 min d'inactivité (réveil ≈ 30 s). `/health` ne touche pas la base (Neon peut aussi s'endormir) ; UptimeRobot et `keepalive.yml` maintiennent l'API éveillée, et le front affiche un écran d'attente explicite si le serveur se réveille.

## Mot de passe oublié

En production (hébergement gratuit), l'e-mail part par l'API HTTPS de Brevo (`EMAIL_API_KEY`, `EMAIL_FROM`), car Render bloque le SMTP sur son offre gratuite. Le SMTP (`SMTP_*`) reste utilisable en local. En local sans fournisseur, le lien s'affiche dans les logs (`dev_reset_link`).
## Structure

```
backend/    API, migrations Alembic, scripts, tests pytest
frontend/   Application React (src/, public/ avec manifest PWA, _headers, _redirects)
docs/       Guide de déploiement gratuit · PEDAGOGIE.md (moteur BKT, limites)
.github/    CI, keepalive, sauvegarde
```

## Sécurité

Aucun secret dans le dépôt (`.env` ignoré). Journaux structurés sans données personnelles, Sentry avec `send_default_pii=False`, limitation de débit, quota LLM quotidien, délimitation des documents importés contre l'injection de prompt, CSP stricte côté front. **Si une clé API a déjà été committée ou partagée, révoquez-la immédiatement.**

## Licence

MIT — voir [LICENSE](LICENSE).

## Bilingue FR / EN de bout en bout

- La langue choisie dans l'interface voyage sur **chaque requête** (`Accept-Language: fr|en`, défaut `fr`).
- Le backend la lit (`get_lang`) et ajoute une règle de langue à **tous** les prompts IA (tuteur, quiz, exercices, examens, corrections, plans d'étude). Les erreurs, badges et recommandations sont localisés à la réponse (`backend/app/core/i18n.py`).
- La base de connaissances (RAG) reste en français ; le modèle répond en anglais à partir de celle-ci.
- Les thèmes sont des identifiants français (historique de maîtrise stable) ; seuls les libellés sont traduits.
- La langue est verrouillée pendant un examen blanc. La voix suit la matière (Anglais → voix anglaise).
- À vérifier à la main avec une vraie clé OpenAI : tuteur, quiz, exercice, examen, plan d'étude, erreurs, badges, PDF, voix — en FR puis en EN.
