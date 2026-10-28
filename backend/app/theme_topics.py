"""
Petite table de correspondance matiere+niveau -> theme par defaut, utilisee
par le mode Examen blanc qui doit generer des questions en serie sans demander
a l'eleve de choisir un theme a chaque fois. Reprend (en miroir cote backend)
la logique de TOPICS_BY_LEVEL du fichier frontend/src/theme.ts pour rester
coherent niveau par niveau.
"""

DEFAULT_TOPICS = {
    "mathematiques": {
        "primaire": "Additions et soustractions",
        "college": "Équations 1er degré",
        "lycee": "Équations 2nd degré",
        "universite": "Intégrales avancées",
    },
    "physique": {
        "primaire": "États de la matière",
        "college": "Vitesse et mouvement",
        "lycee": "Mécanique newtonienne",
        "universite": "Mécanique analytique",
    },
    "biologie": {
        "primaire": "Le corps humain",
        "college": "La cellule",
        "lycee": "Génétique moléculaire",
        "universite": "Biochimie enzymatique",
    },
    "chimie": {
        "primaire": "Mélanges simples",
        "college": "Atomes et molécules",
        "lycee": "Acide-base (pH, pKa)",
        "universite": "Mécanismes SN1/SN2/E1/E2",
    },
    "francais": {
        "primaire": "Conjugaison simple",
        "college": "Figures de style",
        "lycee": "Dissertation",
        "universite": "Théorie littéraire",
    },
    "anglais": {
        "primaire": "Présent simple",
        "college": "Tous les temps",
        "lycee": "Conditionnels",
        "universite": "Academic writing",
    },
    "histoire": {
        "primaire": "Fêtes nationales",
        "college": "Révolution française",
        "lycee": "2ème Guerre Mondiale",
        "universite": "Historiographie",
    },
    "informatique": {
        "primaire": "Scratch — séquences",
        "college": "Python basique",
        "lycee": "Algorithmes de tri",
        "universite": "NP-complétude",
    },
}


def get_default_topic(subject: str, level: str) -> str:
    return DEFAULT_TOPICS.get(subject, {}).get(level) or DEFAULT_TOPICS["mathematiques"]["lycee"]
