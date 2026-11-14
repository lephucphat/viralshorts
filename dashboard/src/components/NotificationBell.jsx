import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, CheckCircle2, AlertTriangle, Gem } from 'lucide-react';
import { useLang } from '../contexts/LangContext';
import { inboxApi, timeAgo } from '../lib/studio';

const POLL_MS = 60000;

// What each kind of notification shows and where it leads. The server stores only the kind, a
// reference and a little data, so the wording lives here (in the reader's language).
function describe(item, t) {
  const title = item.data?.title || '';
  switch (item.kind) {
    case 'clips_ready':
      return { icon: CheckCircle2, tone: 'text-ok', href: `#/project/${item.ref}`,
        head: t('bell.clips_ready'), body: t('bell.clips_ready.body', { title, n: item.data?.count || 0 }) };
    case 'job_failed':
      return { icon: AlertTriangle, tone: 'text-danger', href: `#/project/${item.ref}`,
        head: t('bell.job_failed'), body: title };
    case 'low_credits':
      return { icon: Gem, tone: 'text-warn', href: '#/pricing', head: t('bell.low_credits'), body: t('bell.low_credits.body') };
    default:
      return null;
  }
}

// The bell in the app header: a badge with the unread count and a short list of what happened.
export default function NotificationBell() {
  const { t, lang } = useLang();
  const [state, setState] = useState({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);
  const root = useRef(null);

  const load = useCallback(() => {
    inboxApi.list().then(setState).catch(() => { /* the bell is a convenience */ });
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (!open) return undefined;
    load();
    const onDown = (e) => { if (root.current && !root.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, load]);

  const readOne = (item) => {
    setOpen(false);
    if (item.read) return;
    setState((s) => ({ items: s.items.map((i) => (i.id === item.id ? { ...i, read: true } : i)), unread: Math.max(0, s.unread - 1) }));
    inboxApi.read(item.id).catch(() => {});
  };
  const readAll = () => {
    setState((s) => ({ items: s.items.map((i) => ({ ...i, read: true })), unread: 0 }));
    inboxApi.read().catch(() => {});
  };

  return (
    <div className="relative" ref={root}>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-haspopup="dialog" aria-expanded={open}
        aria-label={state.unread ? t('bell.aria.unread', { n: state.unread }) : t('bell.aria')}
        className="relative w-9 h-9 rounded-full border border-rule-2 text-ink2 hover:bg-paper2 flex items-center justify-center transition-colors">
        <Bell size={16} />
        {state.unread > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-brand text-brassink text-[0.6875rem] font-semibold leading-[18px] text-center">
            {state.unread > 9 ? '9+' : state.unread}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label={t('bell.title')}
          className="absolute right-0 z-40 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] rounded-xl bg-paper border border-rule-2 shadow-pop animate-fade overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-rule">
            <span className="text-sm font-semibold text-ink">{t('bell.title')}</span>
            {state.unread > 0 && (
              <button type="button" onClick={readAll} className="text-xs text-brass hover:underline">{t('bell.read_all')}</button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto custom-scrollbar">
            {state.items.map((item) => {
              const d = describe(item, t);
              if (!d) return null;
              const Icon = d.icon;
              return (
                <li key={item.id}>
                  <a href={d.href} onClick={() => readOne(item)}
                    className={`flex gap-3 px-4 py-3 hover:bg-paper2 transition-colors ${item.read ? '' : 'bg-accent-soft/40'}`}>
                    <Icon size={18} className={`shrink-0 mt-0.5 ${d.tone}`} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm text-ink font-medium">{d.head}</span>
                      {d.body && <span className="block text-xs text-muted truncate">{d.body}</span>}
                      <span className="block text-[0.6875rem] text-muted mt-0.5">{timeAgo(item.created_at, lang)}</span>
                    </span>
                    {!item.read && <span className="w-2 h-2 rounded-full bg-brass shrink-0 mt-2" aria-hidden="true" />}
                  </a>
                </li>
              );
            })}
          </ul>
          {state.items.length === 0 && <p className="px-4 py-8 text-sm text-muted text-center">{t('bell.empty')}</p>}
        </div>
      )}
    </div>
  );
}
