import { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useLang } from '../../contexts/LangContext';

// A password input with a show/hide toggle. The toggle is a real button with a
// label, so it works with a keyboard and a screen reader, and it never submits.
export default function PasswordField({ label, value, onChange, autoComplete, hint, error, autoFocus = false }) {
  const { t } = useLang();
  const [shown, setShown] = useState(false);
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="eyebrow">{label}</label>
      <div className="relative mt-1.5">
        <input id={id} className={`input-field pr-12 ${error ? '!border-danger' : ''}`}
          type={shown ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete} autoFocus={autoFocus} aria-invalid={error ? 'true' : undefined}
          aria-describedby={hint ? `${id}-hint` : undefined} />
        <button type="button" onClick={() => setShown((v) => !v)} aria-pressed={shown}
          aria-label={shown ? t('auth.hide') : t('auth.show')}
          className="absolute inset-y-0 right-1.5 my-auto h-9 w-9 flex items-center justify-center rounded-full text-muted hover:text-ink hover:bg-paper3 transition-colors">
          {shown ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
      {hint && <div id={`${id}-hint`} className="mt-2">{hint}</div>}
    </div>
  );
}
