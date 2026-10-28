"""Génère une SECRET_KEY aléatoire (JWT) : ``python scripts/generate_secret.py``.

Copiez la valeur dans la variable d'environnement SECRET_KEY de Render (jamais dans le code).
"""

import secrets


def main() -> None:
    """Affiche une clé de 86 caractères URL-safe (512 bits d'entropie)."""
    print(secrets.token_urlsafe(64))


if __name__ == "__main__":
    main()
