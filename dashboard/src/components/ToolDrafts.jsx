import { useEffect, useState, useCallback } from 'react';
import { Image as ImageIcon, Trash2 } from 'lucide-react';
import { getApiUrl } from '../config';
import { draftsApi } from '../lib/studio';
import { useT } from '../contexts/LangContext';

const TOTAL_STEPS = 5;

// Unfinished work in a tool, listed like draft projects: open one to carry on where you stopped.
// Renders nothing when there are none (or the server keeps no drafts).
export default function ToolDrafts({ kind = 'thumbnails', toolId = 'thumbnails' }) {
  const t = useT();
  const [items, setItems] = useState(null);

  const load = useCallback(() => {
    draftsApi.list(kind)
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]));
  }, [kind]);

  useEffect(() => { load(); }, [load]);

  const remove = async (e, item) => {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(t('drafts.delete.confirm'))) return;
    try {
      await draftsApi.remove(item.id);
      setItems((cur) => (cur || []).filter((x) => x.id !== item.id));
    } catch { /* leave it listed; the next load will tell the truth */ }
  };

  if (!items || items.length === 0) return null;

  return (
    <section className="mt-10" aria-label={t('drafts.title')}>
      <h2 className="eyebrow mb-1">{t('drafts.title')}</h2>
      <p className="text-xs text-muted mb-4">{t('drafts.sub')}</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {items.map((d) => (
          <a key={d.id} href={`#/tools/${toolId}/${d.id}`} className="card card-hover overflow-hidden block group">
            <div className="relative aspect-video bg-paper3 flex items-center justify-center">
              {d.preview
                ? <img src={getApiUrl(d.preview)} alt="" loading="lazy" className="w-full h-full object-cover" />
                : <ImageIcon size={28} className="text-muted" />}
              <span className="absolute top-2 left-2 chip">{t('drafts.badge')}</span>
              <button type="button" onClick={(e) => remove(e, d)} aria-label={t('drafts.delete')}
                      className="absolute top-2 right-2 btn-quiet opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity">
                <Trash2 size={14} />
              </button>
            </div>
            <div className="p-3.5">
              <p className="text-sm text-ink truncate">{d.title || t('drafts.untitled')}</p>
              <p className="text-xs text-muted mt-1">
                {t('drafts.step', { n: Math.min(d.step + 1, TOTAL_STEPS), total: TOTAL_STEPS })}
                {' · '}{new Date(d.updated_at * 1000).toLocaleString()}
              </p>
            </div>
          </a>
        ))}
      </div>
    </section>
  );
}
