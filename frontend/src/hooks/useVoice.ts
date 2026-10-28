import { useCallback, useEffect, useRef, useState } from "react";
import { translate, getLang, type Lang } from "../i18n";

/**
 * Voix : reconnaissance (parole → texte) et synthèse (texte → parole) via les API natives du
 * navigateur : gratuit, aucun appel serveur. La qualité dépend du navigateur et du système ;
 * le bouton micro est masqué quand l'API n'existe pas.
 */

interface RecognitionResultEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}
interface RecognitionErrorEvent {
  error: string;
}
interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  start(): void;
  stop(): void;
}
type RecognitionCtor = new () => SpeechRecognitionLike;
type SpeechWindow = Window & { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };

function recognitionCtor(): RecognitionCtor | undefined {
  if (typeof window === "undefined") return undefined;
  const w = window as SpeechWindow;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

const SPEECH_LANG = { fr: "fr-FR", en: "en-GB" } as const;

export function useSpeechRecognition(onResult: (text: string) => void) {
  const [error, setError] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  const isSupported = recognitionCtor() !== undefined;
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor || isListening) return;
    setError(null);
    const recognition = new Ctor();
    recognition.lang = SPEECH_LANG[getLang()];
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript;
      if (transcript) onResultRef.current(transcript);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = (event) => {
      setIsListening(false);
      const known: Record<string, string> = {
        "not-allowed": translate("voice.notAllowed"),
        "no-speech": translate("voice.noSpeech"),
        "audio-capture": translate("voice.noMic"),
      };
      setError(known[event.error] ?? translate("voice.error", { code: event.error }));
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
      setIsListening(true);
    } catch (e) {
      console.warn("[voice] Démarrage impossible.", e);
      setIsListening(false);
    }
  }, [isListening]);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  useEffect(() => () => recognitionRef.current?.stop(), []);
  return { isListening, isSupported, start, stop, error };
}

/** Nettoie le Markdown/LaTeX avant lecture pour éviter « dièse dièse » ou « crochet ouvrant ». */
function stripForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/\$\$?[^$]+\$\$?/g, ` ${translate("voice.formula")} `)
    .replace(/[#*_`>~]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export function isSpeechSynthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/**
 * Langue de la VOIX de lecture : la matière « Anglais » est lue en anglais même si l'interface est en
 * français (sinon accent français sur des phrases anglaises) ; sinon, langue de l'interface.
 */
export function speechLangFor(subject: string, uiLang: Lang): Lang {
  return subject === "anglais" ? "en" : uiLang;
}

export function speakText(text: string, onEnd?: () => void, lang: Lang = getLang()): boolean {
  if (!isSpeechSynthesisSupported()) return false;
  window.speechSynthesis.cancel(); // une seule lecture à la fois
  const utterance = new SpeechSynthesisUtterance(stripForSpeech(text));
  utterance.lang = SPEECH_LANG[lang];
  utterance.rate = 0.97;
  if (onEnd) {
    utterance.onend = onEnd;
    utterance.onerror = () => onEnd();
  }
  window.speechSynthesis.speak(utterance);
  return true;
}

export function stopSpeaking(): void {
  if (isSpeechSynthesisSupported()) window.speechSynthesis.cancel();
}
