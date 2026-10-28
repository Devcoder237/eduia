import { useId } from "react";
import type { ReactNode } from "react";

interface BaseProps {
  label: string;
  hint?: string;
  error?: string | undefined;
  required?: boolean;
}

export interface TextFieldProps extends BaseProps {
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email" | "password" | "date" | "number" | "search";
  autoComplete?: string;
  placeholder?: string;
  maxLength?: number;
  inputMode?: "text" | "numeric" | "email" | "search";
  disabled?: boolean;
  name?: string;
}

/** Champ texte avec label lié, aide et erreur annoncées aux lecteurs d'écran. */
export function TextField({
  label, hint, error, required, value, onChange, type = "text", autoComplete, placeholder, maxLength, inputMode, disabled, name,
}: TextFieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-err`;
  const describedBy = [hint ? hintId : "", error ? errorId : ""].join(" ").trim() || undefined;
  return (
    <div className="ui-field">
      <label htmlFor={id} className="ui-field__label">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      <input
        id={id}
        name={name}
        className="ui-input"
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        maxLength={maxLength}
        inputMode={inputMode}
        required={required}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
      />
      {hint && <p id={hintId} className="ui-field__hint">{hint}</p>}
      {error && <p id={errorId} className="ui-field__error" role="alert">{error}</p>}
    </div>
  );
}

export interface Option {
  value: string;
  label: string;
}

export interface SelectFieldProps extends BaseProps {
  value: string;
  onChange: (value: string) => void;
  options: readonly Option[];
  disabled?: boolean;
}

export function SelectField({ label, hint, error, required, value, onChange, options, disabled }: SelectFieldProps) {
  const id = useId();
  return (
    <div className="ui-field">
      <label htmlFor={id} className="ui-field__label">{label}</label>
      <select
        id={id}
        className="ui-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {hint && <p className="ui-field__hint">{hint}</p>}
      {error && <p className="ui-field__error" role="alert">{error}</p>}
    </div>
  );
}

export interface TextAreaProps extends BaseProps {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  maxLength?: number;
  placeholder?: string;
  disabled?: boolean;
}

export function TextArea({ label, hint, error, required, value, onChange, rows = 5, maxLength, placeholder, disabled }: TextAreaProps) {
  const id = useId();
  return (
    <div className="ui-field">
      <label htmlFor={id} className="ui-field__label">{label}</label>
      <textarea
        id={id}
        className="ui-input ui-textarea"
        value={value}
        rows={rows}
        maxLength={maxLength}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? true : undefined}
      />
      {hint && <p className="ui-field__hint">{hint}</p>}
      {error && <p className="ui-field__error" role="alert">{error}</p>}
    </div>
  );
}

/** Groupe de choix exclusifs (boutons radio visuels) : remplace les listes de boutons non sémantiques. */
export interface ChoiceGroupProps {
  legend: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: ReactNode; sub?: string | undefined; color?: string | undefined }[];
}

export function ChoiceGroup({ legend, value, onChange, options }: ChoiceGroupProps) {
  const groupName = useId(); // unique : deux groupes identiques (tiroir + panneau) ne se perturbent pas
  return (
    <fieldset className="ui-choice">
      <legend className="ui-choice__legend">{legend}</legend>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <label key={o.value} className={`ui-choice__item${selected ? " is-selected" : ""}`}>
            <input
              type="radio"
              className="ui-choice__input"
              name={groupName}
              value={o.value}
              checked={selected}
              onChange={() => onChange(o.value)}
            />
            <span className="ui-choice__dot" style={selected && o.color ? { background: o.color, borderColor: o.color } : undefined} aria-hidden="true" />
            <span className="ui-choice__label">{o.label}</span>
            {o.sub && <span className="ui-choice__sub">{o.sub}</span>}
          </label>
        );
      })}
    </fieldset>
  );
}
