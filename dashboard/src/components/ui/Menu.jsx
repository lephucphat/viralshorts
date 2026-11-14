import { useEffect, useRef, useState } from 'react';

/**
 * Small dropdown menu. Closes on outside click, Escape and after a choice.
 *
 * Props:
 *  - trigger: (props) => node   gets { onClick, 'aria-haspopup', 'aria-expanded', ref }
 *  - items: [{ id, label, icon?, danger?, disabled?, onSelect }]  (a falsy item is skipped)
 *  - align: 'left' | 'right'
 */
export default function Menu({ trigger, items, align = 'right' }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (root.current && !root.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="relative inline-block" ref={root}>
      {trigger({ onClick: () => setOpen((v) => !v), 'aria-haspopup': 'menu', 'aria-expanded': open })}
      {open && (
        <div
          role="menu"
          className={`absolute z-40 mt-2 min-w-[11rem] py-1.5 rounded-xl bg-paper border border-rule-2 shadow-pop animate-fade ${align === 'right' ? 'right-0' : 'left-0'}`}
        >
          {items.filter(Boolean).map((it) => (
            <button
              key={it.id}
              type="button"
              role="menuitem"
              disabled={it.disabled}
              onClick={() => { setOpen(false); it.onSelect?.(); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2 text-sm text-left transition-colors hover:bg-paper2 disabled:opacity-40 ${it.danger ? 'text-danger' : 'text-ink2 hover:text-ink'}`}
            >
              {it.icon}
              {it.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
