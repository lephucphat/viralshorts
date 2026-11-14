/**
 * Underline tabs. Props: tabs [{ id, label, count? }], value, onChange(id).
 * Keyboard: left/right arrows move between tabs.
 */
export default function Tabs({ tabs, value, onChange, className = '' }) {
  const onKey = (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const i = tabs.findIndex((t) => t.id === value);
    const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    onChange(next.id);
  };
  return (
    <div role="tablist" onKeyDown={onKey} className={`flex flex-wrap gap-1 border-b border-rule ${className}`}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          tabIndex={value === t.id ? 0 : -1}
          onClick={() => onChange(t.id)}
          className="tab inline-flex items-center gap-2"
        >
          {t.label}
          {t.count != null && <span className="readout !normal-case">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}
