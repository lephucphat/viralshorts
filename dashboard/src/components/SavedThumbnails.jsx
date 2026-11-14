import { useEffect, useState, useCallback } from 'react';
import { Download, Trash2, Loader2 } from 'lucide-react';
import { getApiUrl } from '../config';
import { apiFetch } from '../lib/api';
import { useT } from '../contexts/LangContext';

// The thumbnails this account has made before, kept on the server so they are still here after
// leaving the page. Renders nothing when there are none (or when the server has no library).
export default function SavedThumbnails() {
  const t = useT();
  const [items, setItems] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(() => {
    apiFetch('/api/assets?kind=thumbnail')
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((data) => setItems(data.items || []))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => { load(); }, [load]);

  const download = async (item) => {
    try {
      const blob = await (await fetch(getApiUrl(item.url))).blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = item.url.split('/').pop() || 'thumbnail.jpg';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(href);
    } catch {
      window.open(getApiUrl(item.url), '_blank');
    }
  };

  const remove = async (item) => {
    if (!window.confirm(t('ts.saved.confirm'))) return;
    setBusyId(item.id);
    try {
      const res = await apiFetch(`/api/assets/${item.id}`, { method: 'DELETE' });
      if (res.ok) setItems((cur) => (cur || []).filter((x) => x.id !== item.id));
    } finally {
      setBusyId(null);
    }
  };

  if (items === null) {
    return (
      <div className="mt-10 flex items-center gap-2 text-xs text-muted">
        <Loader2 size={12} className="animate-spin" /> {t('ts.saved.loading')}
      </div>
    );
  }
  if (items.length === 0) return null;

  return (
    <section className="mt-10" aria-label={t('ts.saved.title')}>
      <h2 className="eyebrow mb-1">{t('ts.saved.title')}</h2>
      <p className="text-xs text-muted mb-4">{t('ts.saved.sub')}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {items.map((item) => (
          <figure key={item.id} className="card overflow-hidden group">
            <div className="relative">
              <img src={getApiUrl(item.url)} alt={item.text || item.title} loading="lazy"
                   className="w-full aspect-video object-cover bg-paper3" />
              <div className="absolute inset-x-0 bottom-0 p-2 flex justify-end gap-2 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                <button type="button" onClick={() => download(item)} className="btn-quiet" aria-label={t('ugc.download')}>
                  <Download size={14} />
                </button>
                <button type="button" onClick={() => remove(item)} disabled={busyId === item.id}
                        className="btn-quiet" aria-label={t('ts.saved.delete')}>
                  {busyId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
            <figcaption className="p-2.5">
              <p className="text-xs text-ink truncate">{item.title}</p>
              <p className="text-[11px] text-muted mt-0.5">
                {new Date(item.created_at * 1000).toLocaleDateString()}
              </p>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
