/**
 * Catalogue des matières, niveaux et modes pédagogiques.
 *
 * Les couleurs servent de FOND (texte blanc dessus, contraste >= 4,5:1 vérifié) et de
 * liseré décoratif : elles ne portent jamais seules une information (l'étiquette est toujours
 * affichée) et ne sont jamais utilisées comme couleur de texte sur fond de page.
 *
 * Les libellés affichés viennent de l'i18n (`labelKey`). Les thèmes restent des IDENTIFIANTS français
 * (envoyés au serveur, clés de l'historique de maîtrise) ; leur libellé anglais est dans topicsEn.ts
 * (`topicLabel`). Les questions rapides existent dans les deux langues (`getQuickQuestions`).
 */

import type { Lang, TranslationKey } from "./i18n";
import { QUICK_QUESTIONS_EN, TOPIC_LABELS_EN } from "./topicsEn";

export type Subject = { id: string; labelKey: TranslationKey; label: string; icon: string; color: string };
export type Level = { id: string; labelKey: TranslationKey; subKey: TranslationKey; label: string; icon: string; color: string; simplified: boolean };
export type Mode = { id: string; labelKey: TranslationKey; descKey: TranslationKey; label: string; icon: string; color: string };

export const SUBJECTS: Subject[] = [
  { id: "mathematiques", labelKey: "subject.mathematiques", label: "Mathématiques", icon: "📐", color: "#3D7A5C" },
  { id: "physique",      labelKey: "subject.physique",      label: "Physique",       icon: "⚡", color: "#3E6FA6" },
  { id: "biologie",      labelKey: "subject.biologie",      label: "Biologie",       icon: "🧬", color: "#58762B" },
  { id: "chimie",        labelKey: "subject.chimie",        label: "Chimie",         icon: "🧪", color: "#8A6212" },
  { id: "francais",      labelKey: "subject.francais",      label: "Français",       icon: "📖", color: "#8C3B4A" },
  { id: "anglais",       labelKey: "subject.anglais",       label: "Anglais",        icon: "🌍", color: "#6B4A8C" },
  { id: "histoire",      labelKey: "subject.histoire",      label: "Histoire",       icon: "🏛️", color: "#7A5C3E" },
  { id: "informatique",  labelKey: "subject.informatique",  label: "Informatique",   icon: "💻", color: "#2A7664" },
];

export const LEVELS: Level[] = [
  { id: "primaire",   labelKey: "level.primaire",   subKey: "level.primaire.sub",   label: "Primaire",   icon: "🧸", color: "#9A5A12", simplified: true },
  { id: "college",    labelKey: "level.college",    subKey: "level.college.sub",    label: "Collège",    icon: "🎒", color: "#3F7490", simplified: false },
  { id: "lycee",      labelKey: "level.lycee",      subKey: "level.lycee.sub",      label: "Lycée",      icon: "🎓", color: "#A84A2A", simplified: false },
  { id: "universite", labelKey: "level.universite", subKey: "level.universite.sub", label: "Université", icon: "🏛️", color: "#5B5470", simplified: false },
];

/** Modes de conversation du tuteur (l'exercice et le quiz ont leur propre page). */
export const MODES: Mode[] = [
  { id: "explain",  labelKey: "mode.explain",  descKey: "mode.explain.desc",  label: "Expliquer", icon: "📚", color: "#3E6FA6" },
  { id: "socratic", labelKey: "mode.socratic", descKey: "mode.socratic.desc", label: "Socrate",   icon: "🤔", color: "#8A6212" },
];

export const getSubject = (id: string): Subject => SUBJECTS.find((s) => s.id === id) ?? SUBJECTS[0]!;
export const getLevel = (id: string): Level => LEVELS.find((l) => l.id === id) ?? LEVELS[2]!;
export const getMode = (id: string): Mode => MODES.find((m) => m.id === id) ?? MODES[0]!;

/**
 * Thèmes proposés pour les Exercices et le Quiz, calibrés par matière ET par niveau.
 * Quand l'utilisateur change de niveau, la liste de thèmes change avec — fini les
 * thèmes "Lycée" proposés à un élève de "Primaire".
 */
export const TOPICS_BY_LEVEL: Record<string, Record<string, string[]>> = {
  mathematiques: {
    primaire:   ["Additions", "Soustractions", "Tables de multiplication", "Fractions simples", "Figures géométriques"],
    college:  ["Fractions & décimaux", "Proportionnalité", "Équations 1er degré", "Théorème de Pythagore", "Statistiques"],
    lycee:      ["Équations 2nd degré", "Dérivées", "Suites", "Probabilités", "Trigonométrie"],
    universite: ["Intégrales avancées", "Algèbre linéaire", "Analyse complexe", "Équations différentielles"],
  },
  physique: {
    primaire:   ["États de la matière", "Le poids et la masse", "Lumière et ombre", "Les aimants"],
    college:    ["Vitesse et mouvement", "Électricité simple (U=RI)", "Les forces", "Le son"],
    lycee:      ["Mécanique newtonienne", "Circuits électriques (Kirchhoff)", "Optique géométrique", "Thermodynamique"],
    universite: ["Mécanique analytique", "Électromagnétisme (Maxwell)", "Physique quantique", "Relativité"],
  },
  biologie: {
    primaire:   ["Le corps humain", "Les animaux", "Les plantes", "Les saisons"],
    college:    ["La cellule", "ADN et chromosomes", "Écosystèmes", "Évolution (Darwin)"],
    lycee:      ["Génétique moléculaire", "Immunologie", "Régulation hormonale", "Neurosciences"],
    universite: ["Biochimie enzymatique", "Génomique", "Signalisation cellulaire", "Biologie moléculaire avancée"],
  },
  chimie: {
    primaire:   ["Mélanges simples", "L'eau et ses états", "Solide, liquide, gaz"],
    college:    ["Atomes et molécules", "Mélanges et solutions", "Formules H2O / CO2 / NaCl"],
    lycee:      ["Acide-base (pH, pKa)", "Oxydoréduction", "Chimie organique", "Cinétique chimique"],
    universite: ["Mécanismes SN1/SN2/E1/E2", "Stéréochimie", "Spectroscopie", "Thermochimie avancée"],
  },
  francais: {
    primaire:   ["Lecture et écriture", "Orthographe de base", "Conjugaison simple", "Accord sujet-verbe"],
    college:    ["Figures de style", "Genres littéraires", "La Fontaine & Molière", "Analyse grammaticale"],
    lycee:      ["Dissertation", "Commentaire composé", "Mouvements littéraires", "Hugo, Zola, Baudelaire"],
    universite: ["Théorie littéraire", "Linguistique avancée", "Stylistique", "Littérature comparée"],
  },
  anglais: {
    primaire:   ["To be / to have", "Vocabulaire de base", "Présent simple"],
    college:    ["Tous les temps", "Modaux", "Comparatifs"],
    lycee:      ["Conditionnels", "Discours indirect", "Phrasal verbs", "Essay writing"],
    universite: ["Academic writing", "Linguistique anglaise", "Littérature anglophone"],
  },
  histoire: {
    primaire:   ["Personnages camerounais", "Fêtes nationales", "Monuments historiques"],
    college:    ["Antiquité", "Moyen-Âge", "Révolution française", "Colonisation"],
    lycee:      ["2ème Guerre Mondiale", "Guerre Froide", "Décolonisation africaine", "Indépendance du Cameroun"],
    universite: ["Historiographie", "Critique des sources", "Débats historiques"],
  },
  informatique: {
    primaire:   ["Scratch — séquences", "Scratch — boucles", "Scratch — conditions"],
    college:    ["Pseudo-code", "Python basique", "HTML/CSS"],
    lycee:      ["POO en Python", "Algorithmes de tri", "Complexité O(n)", "SQL"],
    universite: ["Structures avancées (graphes)", "NP-complétude", "Machine Learning", "Systèmes distribués"],
  },
};

const DEFAULT_TOPICS: string[] = ["Équations 2nd degré", "Dérivées", "Suites", "Probabilités"];

export function getTopics(subject: string, level: string): string[] {
  return TOPICS_BY_LEVEL[subject]?.[level] ?? DEFAULT_TOPICS;
}

/**
 * Questions rapides suggérées sur la page Tuteur, calibrées par matière ET par
 * niveau (même logique que TOPICS_BY_LEVEL : avant, les mêmes questions de
 * niveau Lycée s'affichaient pour le niveau Primaire).
 */
export const QUICK_QUESTIONS_BY_LEVEL: Record<string, Record<string, string[]>> = {
  mathematiques: {
    primaire:   ["Combien font 24 + 38 ?", "Comment apprendre les tables de multiplication ?", "C'est quoi un carré et un rectangle ?"],
    college:    ["Comment résoudre une équation du 1er degré ?", "C'est quoi le théorème de Pythagore ?", "Comment calculer un pourcentage ?"],
    lycee:      ["Comment résoudre x² - 5x + 6 = 0 ?", "Explique-moi les dérivées", "Qu'est-ce qu'une suite arithmétique ?"],
    universite: ["Comment calculer une intégrale double ?", "Explique les espaces vectoriels", "C'est quoi une équation différentielle ?"],
  },
  physique: {
    primaire:   ["Pourquoi le ciel est bleu ?", "Comment fonctionne un aimant ?", "C'est quoi la lumière ?"],
    college:    ["C'est quoi la vitesse ?", "Comment fonctionne un circuit électrique simple ?", "Qu'est-ce qu'une force ?"],
    lycee:      ["Explique les lois de Newton", "Comment fonctionne un circuit RLC ?", "C'est quoi la relativité ?"],
    universite: ["Explique le formalisme hamiltonien", "C'est quoi les équations de Maxwell ?", "Qu'est-ce que la mécanique quantique ?"],
  },
  biologie: {
    primaire:   ["Comment fonctionne le cœur ?", "Pourquoi les feuilles sont vertes ?", "C'est quoi un animal vertébré ?"],
    college:    ["C'est quoi une cellule ?", "Comment fonctionne l'ADN ?", "Qu'est-ce qu'un écosystème ?"],
    lycee:      ["Comment fonctionne la photosynthèse ?", "Explique la mitose", "Qu'est-ce que l'immunité ?"],
    universite: ["Explique la signalisation cellulaire", "C'est quoi la génomique ?", "Comment fonctionne la biochimie enzymatique ?"],
  },
  chimie: {
    primaire:   ["C'est quoi un mélange ?", "Pourquoi la glace fond ?", "Quels sont les états de l'eau ?"],
    college:    ["C'est quoi un atome ?", "Comment reconnaître un mélange et une solution ?", "Qu'est-ce qu'une molécule ?"],
    lycee:      ["Comment équilibrer une équation chimique ?", "C'est quoi un acide fort ?", "Explique la liaison covalente"],
    universite: ["Explique les mécanismes SN1/SN2", "C'est quoi la stéréochimie ?", "Comment fonctionne la spectroscopie ?"],
  },
  francais: {
    primaire:   ["Comment conjuguer un verbe au présent ?", "C'est quoi un nom et un verbe ?", "Comment bien écrire les pluriels ?"],
    college:    ["C'est quoi une métaphore ?", "Comment reconnaître les genres littéraires ?", "Qui était La Fontaine ?"],
    lycee:      ["Comment accorder le participe passé ?", "Qu'est-ce que le subjonctif ?", "Aide-moi à analyser un texte"],
    universite: ["C'est quoi la théorie littéraire ?", "Explique la stylistique", "Comment comparer deux œuvres littéraires ?"],
  },
  anglais: {
    primaire:   ["Comment dire 'bonjour' en anglais ?", "C'est quoi 'to be' ?", "Comment compter en anglais ?"],
    college:    ["Quand utiliser le present perfect ?", "C'est quoi les modaux en anglais ?", "Comment faire un comparatif ?"],
    lycee:      ["Explain the present perfect", "When to use 'the'?", "Difference between 'since' and 'for'"],
    universite: ["What is academic writing?", "Explique les nuances culturelles en anglais", "C'est quoi un phrasal verb avancé ?"],
  },
  histoire: {
    primaire:   ["Quelle est la fête nationale du Cameroun ?", "Quels sont les pays voisins du Cameroun ?", "C'est quoi un monument historique ?"],
    college:    ["C'est quoi la colonisation ?", "Explique la Révolution française", "Qu'est-ce que le Moyen-Âge ?"],
    lycee:      ["Explique la 2ème Guerre Mondiale", "C'est quoi la Guerre Froide ?", "Comment s'est faite l'indépendance du Cameroun ?"],
    universite: ["C'est quoi l'historiographie ?", "Comment critiquer une source historique ?", "Quels sont les grands débats historiques actuels ?"],
  },
  informatique: {
    primaire:   ["C'est quoi une boucle sur Scratch ?", "Comment faire bouger un personnage sur Scratch ?", "C'est quoi un ordinateur ?"],
    college:    ["C'est quoi le pseudo-code ?", "Comment écrire ma première boucle en Python ?", "C'est quoi une balise HTML ?"],
    lycee:      ["Explique les pointeurs en C", "C'est quoi la récursivité ?", "Comment fonctionne le tri rapide ?"],
    universite: ["C'est quoi la NP-complétude ?", "Explique le gradient descent", "Comment fonctionne un réseau de neurones ?"],
  },
};

const DEFAULT_QUESTIONS: string[] = ["Comment résoudre x² - 5x + 6 = 0 ?", "Explique-moi les dérivées"];

const DEFAULT_QUESTIONS_EN: string[] = ["How do I solve x² - 5x + 6 = 0?", "Explain derivatives to me"];

/** Questions rapides du tuteur, dans la langue de l'interface (elles sont envoyées telles quelles au tuteur). */
export function getQuickQuestions(subject: string, level: string, lang: Lang = "fr"): string[] {
  if (lang === "en") return [...(QUICK_QUESTIONS_EN[subject]?.[level] ?? DEFAULT_QUESTIONS_EN)];
  return QUICK_QUESTIONS_BY_LEVEL[subject]?.[level] ?? DEFAULT_QUESTIONS;
}

/**
 * Libellé d'un thème dans la langue de l'interface. Le thème lui-même (identifiant français) est
 * toujours ce qui est envoyé au serveur ; un thème inconnu (saisie libre, concept généré) est affiché tel quel.
 */
export function topicLabel(topic: string, lang: Lang): string {
  return lang === "en" ? (TOPIC_LABELS_EN[topic] ?? topic) : topic;
}
