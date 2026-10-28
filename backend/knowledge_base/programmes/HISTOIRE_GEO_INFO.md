# Programme Histoire-Géographie et Informatique — MINESEC Cameroun

## HISTOIRE-GÉOGRAPHIE

### Collège — Histoire

**Antiquité**
- Égypte ancienne : pharaons, pyramides, hiéroglyphes, Nil
- Grèce antique : cité-États (Athènes, Sparte), démocratie, Jeux Olympiques
- Empire romain : Jules César, Auguste, expansion, chute en 476 ap. J.-C.

**Moyen-Âge (Ve – XVe siècle)**
- Féodalité : seigneurs, vassaux, serfs
- Croisades : expéditions chrétiennes vers Jérusalem (1095-1291)
- Islam : naissance en 622, expansion en Afrique du Nord et Afrique sub-saharienne
- Grands royaumes africains : Ghana, Mali (Mansa Moussa), Songhaï, Kanem-Bornou (proche Cameroun)

**Colonisation de l'Afrique**
- Conférence de Berlin (1884-1885) : partage de l'Afrique entre puissances européennes
- Cameroun : protectorat allemand (1884), puis mandat franco-britannique après 1919
- Résistance : Martin-Paul Samba, Rudolf Manga Bell (résistants camerounais pendus par les Allemands)

**Première Guerre Mondiale (1914-1918)**
- Causes : nationalism, impérialisme, alliances, assassinat de François-Ferdinand
- Front occidental : tranchées, Verdun, Somme
- Conséquences : Traité de Versailles, création SDN, perte des colonies allemandes

### Lycée — Histoire

**Décolonisation Africaine**
- Après 1945 : mouvement des indépendances
- **Cameroun** :
  - 1955 : interdiction de l'UPC (Union des Populations du Cameroun)
  - 1er janvier **1960** : Indépendance du Cameroun français
  - 1er octobre **1961** : Réunification avec le Southern Cameroons (ancien Cameroun britannique)
  - Ruben Um Nyobè (fondateur UPC, assassiné 1958), Félix-Roland Moumié (empoisonné 1960)
  - Ahmadou Ahidjo : 1er président (1960-1982)
  - Paul Biya : président depuis 1982

**Guerre Froide (1947-1991)**
- Bloc occidental (USA, OTAN) vs Bloc soviétique (URSS, Pacte de Varsovie)
- Doctrine Truman, Plan Marshall
- Crise des missiles de Cuba (1962)
- Chute du mur de Berlin (9 novembre 1989)
- Dissolution de l'URSS (1991)

**Les Deux Guerres Mondiales**
- SGM (1939-1945) : invasion de la Pologne, Holocauste, Hiroshima/Nagasaki, capitulation japonaise 2 sept. 1945
- Procès de Nuremberg, création de l'ONU (1945)

---

### Géographie — Cameroun et Afrique

**Géographie du Cameroun**
- Superficie : 475 442 km² — surnommé "Afrique en miniature"
- Capitale politique : **Yaoundé** | Capitale économique : **Douala**
- Population : ~28 millions (2024), +250 ethnies
- Régions (10) : Adamaoua, Centre, Est, Extrême-Nord, Littoral, Nord, Nord-Ouest, Ouest, Sud, Sud-Ouest
- Relief : plaines côtières → plateau central (Adamaoua) → montagnes (Ouest) → plaines sahéliennes (Nord)
- Fleuves : Sanaga (principal), Wouri, Bénoué, Nyong, Logone
- Point culminant : Mont Cameroun (4 095 m) — volcan actif

**Économie du Cameroun**
- Agriculture : cacao (1er producteur africain), café, coton, banane, huile de palme, caoutchouc
- Ressources naturières : pétrole (Kribi), bois (forêt du bassin du Congo), bauxite, fer (Mbalam)
- Industries : agroalimentaire (SOSUCAM, CDC), brasseries, cimenteries
- Échanges : port autonome de Douala (principal port d'Afrique centrale)

**Afrique — Grands Ensembles**
- Afrique du Nord (Maghreb) : désert du Sahara, Islam majoritaire
- Afrique subsaharienne : forêt équatoriale (bassin du Congo), savane, Sahel
- Grands fleuves : Nil (6 650 km), Congo, Niger, Zambèze, Sénégal
- Grands lacs africains : Victoria, Tanganyika, Malawi, Tchad

---

## INFORMATIQUE — TIC (Série TI)

### Algorithmique et Programmation

**Bases de l'Algorithmique**
```
Algorithme = Séquence d'instructions pour résoudre un problème
Structure : DEBUT ... FIN
Variables : entier, réel, chaîne, booléen
Affectation : variable ← valeur
```

**Structures de Contrôle**
```
// Condition
SI condition ALORS
    instructions
SINON
    autres instructions
FIN SI

// Boucle bornée
POUR i DE 1 A n FAIRE
    instructions
FIN POUR

// Boucle non bornée
TANT QUE condition FAIRE
    instructions
FIN TANT QUE
```

**Python — Programme Lycée Série TI**
```python
# Variables et types
nom = "Amina"  # str
age = 17  # int
moyenne = 14.5  # float
admis = True  # bool


# Fonctions
def calculer_moyenne(notes):
    return sum(notes) / len(notes)


# Listes
notes = [12, 15, 18, 10, 16]
print(f"Moyenne : {calculer_moyenne(notes):.2f}")

# Dictionnaires
eleve = {"nom": "Jean-Paul", "classe": "Tle C", "moyenne": 14.5}
```

**Bases de Données — SQL**
```sql
-- Créer une table
CREATE TABLE eleves (
    id INTEGER PRIMARY KEY,
    nom VARCHAR(50),
    prenom VARCHAR(50),
    classe VARCHAR(20),
    moyenne FLOAT
);

-- Insérer
INSERT INTO eleves VALUES (1, 'Mbida', 'Paul', 'Tle C', 14.5);

-- Sélectionner
SELECT nom, moyenne FROM eleves WHERE moyenne >= 10;

-- Trier
SELECT * FROM eleves ORDER BY moyenne DESC;
```

**Réseaux Informatiques**
- Protocoles : TCP/IP, HTTP, HTTPS, FTP, SMTP
- Adresse IP : 192.168.1.1 (IPv4), format xxx.xxx.xxx.xxx
- DNS : traduit nom de domaine → adresse IP
- Modèle OSI : 7 couches (Physique → Liaison → Réseau → Transport → Session → Présentation → Application)

**Sécurité Informatique**
- Chiffrement : symétrique (AES) vs asymétrique (RSA)
- Mots de passe : longueur ≥ 12 caractères, mélange majuscules/chiffres/symboles
- Menaces : virus, phishing, ransomware, injection SQL
- Bonnes pratiques : sauvegardes régulières, mises à jour, antivirus
