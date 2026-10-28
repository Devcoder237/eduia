import { useT } from "../i18n";
import { SelectField } from "./ui";
import { LEVELS, SUBJECTS, getTopics, topicLabel } from "../theme";

export interface ContextPickerProps {
  subject: string;
  level: string;
  onSubject: (id: string) => void;
  onLevel: (id: string) => void;
  /** Si fourni, affiche aussi le choix du thème (liste adaptée à la matière ET au niveau). */
  topic?: string;
  onTopic?: (topic: string) => void;
  disabled?: boolean;
}

/** Sélecteurs matière / niveau / thème partagés par les exercices, le quiz et les examens. */
export function ContextPicker({ subject, level, onSubject, onLevel, topic, onTopic, disabled }: ContextPickerProps) {
  const { t, lang } = useT();
  const topics = getTopics(subject, level);
  return (
    <div className="picker">
      <SelectField
        label={t("common.subject")}
        value={subject}
        onChange={onSubject}
        disabled={disabled}
        options={SUBJECTS.map((s) => ({ value: s.id, label: `${s.icon} ${t(s.labelKey)}` }))}
      />
      <SelectField
        label={t("common.level")}
        value={level}
        onChange={onLevel}
        disabled={disabled}
        options={LEVELS.map((l) => ({ value: l.id, label: `${l.icon} ${t(l.labelKey)}` }))}
      />
      {onTopic && topic !== undefined && (
        <SelectField
          label={t("common.topic")}
          value={topic}
          onChange={onTopic}
          disabled={disabled}
          options={topics.map((x) => ({ value: x, label: topicLabel(x, lang) }))}
        />
      )}
    </div>
  );
}
