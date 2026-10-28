import { useCallback, useState } from "react";
import { readPref, writePref } from "../utils/storage";
import { LEVELS, MODES, SUBJECTS } from "../theme";

function pick(key: string, allowed: readonly string[], fallback: string): string {
  const stored = readPref(key);
  return stored !== null && allowed.includes(stored) ? stored : fallback;
}

/** Matière, niveau et mode préférés (partagés entre le tuteur, les exercices et le quiz). */
export function useTutorPrefs() {
  const [subject, setSubjectState] = useState(() => pick("pref_subject", SUBJECTS.map((s) => s.id), "mathematiques"));
  const [level, setLevelState] = useState(() => pick("pref_level", LEVELS.map((l) => l.id), "lycee"));
  // « exercise » et « quiz » ont leur page dédiée : une ancienne valeur enregistrée retombe sur « explain ».
  const [mode, setModeState] = useState(() => pick("pref_mode", MODES.map((m) => m.id), "explain"));

  const setSubject = useCallback((value: string) => { setSubjectState(value); writePref("pref_subject", value); }, []);
  const setLevel = useCallback((value: string) => { setLevelState(value); writePref("pref_level", value); }, []);
  const setMode = useCallback((value: string) => { setModeState(value); writePref("pref_mode", value); }, []);

  return { subject, level, mode, setSubject, setLevel, setMode };
}
