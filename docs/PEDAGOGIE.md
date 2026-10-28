# Moteur pédagogique — ce qui est modélisé, et ses limites

Ce document sert aussi de base à la section « méthodologie » du mémoire.

## 1. Suivi de maîtrise (BKT, `MasteryTracker`)

| Élément | Choix | Pourquoi |
|---|---|---|
| Hasard (guess) | QCM 0,25 · réponse rédigée 0,05 · défaut 0,10 | Un QCM à 4 options se réussit au hasard une fois sur quatre : une bonne réponse prouve moins qu'un exercice rédigé. |
| Étourderie (slip) | QCM 0,08 · rédigé 0,10 | Valeurs usuelles de la littérature. |
| Indices | +0,15 de hasard par indice (plafond 0,60) | Une réussite aidée prouve moins. |
| Confiance « je devine » | compte comme un indice | Réussite probablement due au hasard. |
| Oubli | `exp(-t / stabilité)`, vers l'a priori 0,30 (jamais en dessous) | Un concept oublié n'est pas pire qu'un concept inconnu. |
| Stabilité | 30 j au départ ; ×2 après réussite, ×1,2 si aidée, ×0,5 après échec (3 à 365 j) | Principe de la répétition espacée. |
| Score d'une matière | moyenne des concepts pondérée par le nombre de tentatives (plafonné à 5) | Un concept essayé une fois ne pèse pas autant qu'un concept travaillé. |

**Limite essentielle :** ces paramètres viennent de la littérature, pas d'élèves camerounais. Calibrer avec `python -m scripts.export_bkt_data --salt <sel>` puis pyBKT (voir l'en-tête du script) dès ~300 réponses réelles.

## 2. Répétition espacée
`get_due_reviews()` repère les concepts appris (maîtrise ≥ 0,5) dont la rétention prévue passe sous 70 %. Ils apparaissent dans les recommandations avec la raison « À revoir (répétition espacée) — rétention estimée X % ».

## 3. Thèmes et prérequis (`services/topics.py`)
Les variantes (« Les fractions », fautes de frappe) sont rattachées à une clé déjà stockée. Le graphe de prérequis n'est qu'un **point de départ** à faire valider par un enseignant du programme.

## 4. Aide socratique graduée
Le tuteur détecte les blocages consécutifs (« je ne sais pas », « I'm stuck »…) : niveau 0 = une question ; niveau 1 = un indice concret ; niveau 2 = une étape modélisée sur un exemple analogue. La réponse finale n'est jamais donnée.

## 5. Qualité des contenus
- **Clé des QCM :** un second appel (température 0) résout la question sans voir la clé ; en cas de désaccord, la question est écartée et régénérée. En cas de panne du vérificateur, la question est conservée. Limite : le même modèle peut se tromper de la même façon. Désactivable : `QUIZ_VERIFY_KEYS=false` (coûte 1 appel IA de plus par question).
- **Banque de questions :** une question validée est réutilisée entre élèves (jamais deux fois au même élève) ; son taux de réussite observé sert d'indicateur de difficulté ; une question dont le taux reste anormalement bas est retirée (`suspect`). Réglages : `QUESTION_BANK_*`.
- **RAG BM25 :** mots rares valorisés, longueur de section normalisée, titre compté double, sigles courts (pH, ADN) conservés ; section trop longue tronquée ; aucun résultat si rien ne correspond.

## 6. Métacognition
Avant la correction, l'élève peut indiquer sa confiance (je devine / plutôt sûr / sûr). L'erreur à confiance 3 (surconfiance) et la réussite à confiance 1 déclenchent un message dédié ; la carte « Confiance en soi » de la page Progrès résume le profil à partir de 10 réponses.

## Migration
`alembic upgrade head` applique `0003_pedagogy` (colonne `learner_profiles.concept_stats`, colonnes `quiz_attempts.confidence` et `bank_id`, table `question_bank_items`). Les profils existants restent compatibles.
