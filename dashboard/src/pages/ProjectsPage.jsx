import { useCallback, useEffect, useRef, useState } from 'react';
import { Search, Upload, Link2, Pencil, Trash2, Heart, FolderPlus, Folder, Plus, X, Loader2, Film, ArrowRight, Archive, MoreVertical, LayoutGrid, List, Clapperboard, Wand2, Send, AlertTriangle } from 'lucide-react';
import StudioShell from '../StudioShell';
import CreateProjectModal from '../components/CreateProjectModal';
import Modal from '../components/ui/Modal';
import Menu from '../components/ui/Menu';
import Tabs from '../components/ui/Tabs';
import EmptyState from '../components/ui/EmptyState';
import ScoreRing from '../components/ui/ScoreRing';
import OnboardingChecklist from '../components/OnboardingChecklist';
import { useLang } from '../contexts/LangContext';
import { projectsApi, collectionsApi, timeAgo, formatDuration } from '../lib/studio';
import { getApiUrl } from '../config';
import { takePendingSource } from '../lib/pendingSource';

const STATUS_TONE = {
  queued: 'badge-brass', processing: 'badge-brass', completed: 'badge-ok',
  failed: 'badge-danger', cancelled: 'badge-warn',
};
const FILTERS = ['', 'active', 'completed', 'favorites', 'failed'];
const SORTS = ['newest', 'oldest', 'score', 'title'];

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}

function ProjectCard({ project, view, onRename, onDelete, onFavorite, onCollect }) {
  const { t, lang } = useLang();
  const active = project.status === 'queued' || project.status === 'processing';
  const failed = project.status === 'failed';
  const list = view === 'list';

  const cover = (
    <div className={`${list ? 'w-40 sm:w-52 shrink-0 aspect-video' : 'aspect-video'} bg-paper3 relative overflow-hidden`}>
      {project.cover_url ? (
        <img src={getApiUrl(project.cover_url)} alt="" loading="lazy" className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
      ) : active ? (
        <div className="skeleton !rounded-none w-full h-full flex items-center justify-center text-muted"><Loader2 size={26} className="animate-spin" /></div>
      ) : (
        <div className="w-full h-full flex items-center justify-center text-muted"><Film size={26} /></div>
      )}
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/55 to-transparent pointer-events-none" />
      {project.duration_seconds > 0 && (
        <span className="absolute right-2.5 bottom-2.5 rounded-md bg-black/70 text-white text-xs font-medium px-2 py-0.5 tabular-nums">
          {formatDuration(project.duration_seconds)}
        </span>
      )}
      <button type="button" onClick={(e) => { e.preventDefault(); e.stopPropagation(); onFavorite(project); }}
        aria-pressed={!!project.favorite} aria-label={t(project.favorite ? 'projects.fav.remove' : 'projects.fav.add')}
        className={`absolute right-2 top-2 w-8 h-8 rounded-full flex items-center justify-center bg-black/45 backdrop-blur-sm transition ${project.favorite ? 'text-pink-400' : 'text-white opacity-0 group-hover:opacity-100 focus:opacity-100'}`}>
        <Heart size={15} fill={project.favorite ? 'currentColor' : 'none'} />
      </button>
      {active && (
        <div className="absolute inset-x-0 bottom-0 h-1 bg-white/25 overflow-hidden">
          {Number.isFinite(project.progress?.percent)
            ? <div className="h-full bg-brand transition-all duration-700" style={{ width: `${Math.max(4, project.progress.percent)}%` }} />
            : <div className="indeterminate-bar h-full w-full" />}
        </div>
      )}
    </div>
  );

  // "Transcribing 63%" / "Step 3 of 4": only what the pipeline actually reported.
  const prog = active && project.progress ? project.progress : null;
  const stageText = prog
    ? (prog.step > 0
      ? `${t(`progress.${prog.stage}`)}${Number.isFinite(prog.percent) ? ` ${prog.percent}%` : ''} · ${t('projects.step', { n: prog.step, total: prog.steps })}`
      : t('progress.queued'))
    : null;

  const body = (
    <div className={`${list ? 'flex-1 min-w-0 py-3 pr-3' : 'p-4 pr-12'}`}>
      <h3 className="text-sm font-semibold text-ink truncate">{project.title}</h3>
      <div className="flex items-center gap-2 mt-2 flex-wrap">
        <span className={STATUS_TONE[project.status] || 'badge-brass'}>
          {active ? t(`projects.stage.${project.status}`) : t(`project.status.${project.status}`)}
        </span>
        {project.status === 'completed' && <span className="readout">{t('projects.clips', { n: project.clip_count })}</span>}
        <span className="readout !normal-case">{timeAgo(project.created_at, lang)}</span>
      </div>
      {stageText && <p className="text-xs text-ink2 mt-2 truncate">{stageText}</p>}
      {failed && (
        <p className="text-xs text-muted mt-2 inline-flex items-center gap-1"><AlertTriangle size={12} className="text-danger" /> {t('projects.failed.hint')}</p>
      )}
      {project.archive?.state === 'available' && (
        <p className="text-xs text-muted mt-2 inline-flex items-center gap-1" title={t('billing.archive.tip')}>
          <Archive size={12} /> {t('billing.archive.until', { date: new Date(project.archive.expires_at * 1000).toLocaleDateString(lang) })}
        </p>
      )}
      {project.archive?.state === 'expired' && <p className="text-xs text-muted mt-2">{t('billing.archive.expired')}</p>}
    </div>
  );

  const score = Number.isFinite(project.top_score) ? (
    <div className={list ? 'px-4 shrink-0' : 'absolute left-3 top-3 rounded-full bg-paper/95 p-1 shadow-card'} title={t('projects.sort.score')}>
      <ScoreRing value={project.top_score} size={list ? 44 : 38} />
    </div>
  ) : null;

  const menu = (
    <Menu
      trigger={(props) => (
        <button type="button" {...props} aria-label={t('projects.menu')}
          className="p-2 rounded-full text-muted hover:text-ink hover:bg-paper3 transition-colors">
          <MoreVertical size={16} />
        </button>
      )}
      items={[
        { id: 'open', label: t('projects.open'), icon: <ArrowRight size={14} />, onSelect: () => { window.location.hash = `#/project/${project.job_id}`; } },
        { id: 'fav', label: t(project.favorite ? 'projects.fav.remove' : 'projects.fav.add'), icon: <Heart size={14} />, onSelect: () => onFavorite(project) },
        { id: 'collect', label: t('collections.add'), icon: <FolderPlus size={14} />, onSelect: () => onCollect(project) },
        { id: 'rename', label: t('projects.rename'), icon: <Pencil size={14} />, onSelect: () => onRename(project) },
        { id: 'delete', label: t('projects.delete'), icon: <Trash2 size={14} />, danger: true, onSelect: () => onDelete(project) },
      ]}
    />
  );

  if (list) {
    return (
      <article className="card card-hover overflow-hidden group relative flex items-center">
        <a href={`#/project/${project.job_id}`} className="flex flex-1 min-w-0 items-center gap-4" aria-label={project.title}>
          {cover}{body}
        </a>
        {score}
        <div className="pr-2">{menu}</div>
      </article>
    );
  }
  return (
    <article className="card card-hover overflow-hidden group relative">
      <a href={`#/project/${project.job_id}`} className="block" aria-label={project.title}>
        <div className="relative">{cover}{score}</div>
        {body}
      </a>
      <div className="absolute right-2 bottom-3">{menu}</div>
    </article>
  );
}

export default function ProjectsPage() {
  const { t } = useLang();
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [sort, setSort] = useState('newest');
  const [link, setLink] = useState('');
  const [creating, setCreating] = useState(null);       // null | { url?, file? }
  const [renaming, setRenaming] = useState(null);
  const [renameTo, setRenameTo] = useState('');
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const linkRef = useRef(null);
  const [view, setView] = useState(() => {
    try { return localStorage.getItem('vs_projects_view') === 'list' ? 'list' : 'grid'; } catch (_) { return 'grid'; }
  });
  const [dragging, setDragging] = useState(false);
  const [collections, setCollections] = useState([]);
  const [collection, setCollection] = useState(null);          // null = every project
  const [collecting, setCollecting] = useState(null);          // the project being filed
  const [memberOf, setMemberOf] = useState([]);                // collection ids it is in
  const [newName, setNewName] = useState('');
  const [collError, setCollError] = useState('');
  const pickView = (v) => { setView(v); try { localStorage.setItem('vs_projects_view', v); } catch (_) { /* best effort */ } };
  const dq = useDebounced(q, 250);

  // A link pasted on the landing page before sign-up opens the create dialog on arrival.
  useEffect(() => {
    const pending = takePendingSource();
    if (pending) setCreating({ url: pending });
  }, []);

  const focusLink = () => {
    linkRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    linkRef.current?.focus({ preventScroll: true });
  };

  const load = useCallback(async (quiet = false) => {
    try {
      const page = await projectsApi.list({
        q: dq, sort, collection,
        status: status === 'favorites' ? '' : status,
        favorite: status === 'favorites',
      });
      setItems(page.items); setTotal(page.total); setLoadError(false);
    } catch (_) {
      if (!quiet) setLoadError(true);
    }
  }, [dq, status, sort, collection]);

  useEffect(() => { load(); }, [load]);

  // Dropping a video anywhere on the page starts a project from it.
  useEffect(() => {
    let depth = 0;
    const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files');
    const enter = (e) => { if (hasFiles(e)) { depth += 1; setDragging(true); } };
    const leave = (e) => { if (hasFiles(e)) { depth = Math.max(0, depth - 1); if (!depth) setDragging(false); } };
    const over = (e) => { if (hasFiles(e)) e.preventDefault(); };
    const drop = (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault(); depth = 0; setDragging(false);
      const f = e.dataTransfer.files?.[0];
      if (f && (f.type.startsWith('video/') || /\.(mkv|mov|mp4|webm)$/i.test(f.name))) setCreating({ file: f });
    };
    window.addEventListener('dragenter', enter);
    window.addEventListener('dragleave', leave);
    window.addEventListener('dragover', over);
    window.addEventListener('drop', drop);
    return () => {
      window.removeEventListener('dragenter', enter);
      window.removeEventListener('dragleave', leave);
      window.removeEventListener('dragover', over);
      window.removeEventListener('drop', drop);
    };
  }, []);

  // Keep running projects fresh without hammering the API when nothing moves.
  const hasActive = (items || []).some((p) => p.status === 'queued' || p.status === 'processing');
  useEffect(() => {
    if (!hasActive) return undefined;
    const id = setInterval(() => load(true), 5000);
    return () => clearInterval(id);
  }, [hasActive, load]);

  const loadCollections = useCallback(async () => {
    try { setCollections((await collectionsApi.list()).items); } catch (_) { /* the row just stays empty */ }
  }, []);
  useEffect(() => { loadCollections(); }, [loadCollections]);

  const toggleFavorite = async (project) => {
    const next = !project.favorite;
    setItems((list) => (list || []).map((p) => (p.job_id === project.job_id ? { ...p, favorite: next } : p)));
    try { await projectsApi.favorite(project.job_id, next); if (status === 'favorites') await load(true); }
    catch (_) { await load(true); }
  };

  const openCollect = async (project) => {
    setCollecting(project); setCollError(''); setNewName(''); setMemberOf([]);
    try { setMemberOf((await projectsApi.collectionIds(project.job_id)).ids); } catch (_) { /* unchecked */ }
  };
  const collErr = (e) => t(`collections.err.${e?.code === 'exists' || e?.code === 'too_many' ? e.code : 'generic'}`);
  const toggleMember = async (c) => {
    const inside = memberOf.includes(c.id);
    try {
      if (inside) await collectionsApi.take(c.id, collecting.job_id); else await collectionsApi.add(c.id, collecting.job_id);
      setMemberOf((ids) => (inside ? ids.filter((x) => x !== c.id) : [...ids, c.id]));
      await loadCollections();
      if (collection === c.id) await load(true);
    } catch (e) { setCollError(collErr(e)); }
  };
  const createCollection = async () => {
    if (!newName.trim()) return;
    try {
      const c = await collectionsApi.create(newName.trim());
      setNewName(''); setCollError('');
      await collectionsApi.add(c.id, collecting.job_id);
      setMemberOf((ids) => [...ids, c.id]);
      await loadCollections();
    } catch (e) { setCollError(collErr(e)); }
  };
  const removeCollection = async (c) => {
    try { await collectionsApi.remove(c.id); if (collection === c.id) setCollection(null); await loadCollections(); }
    catch (_) { /* leave it */ }
  };

  const startFromLink = (e) => {
    e.preventDefault();
    if (link.trim()) setCreating({ url: link.trim() });
  };

  const confirmRename = async () => {
    if (!renaming || !renameTo.trim()) return;
    setBusy(true);
    try { await projectsApi.rename(renaming.job_id, renameTo.trim()); setRenaming(null); await load(true); }
    finally { setBusy(false); }
  };
  const confirmDelete = async () => {
    if (!deleting) return;
    setBusy(true);
    try { await projectsApi.remove(deleting.job_id); setDeleting(null); await load(true); }
    finally { setBusy(false); }
  };

  const empty = items && items.length === 0;
  const filtering = !!(dq || status);

  return (
    <StudioShell active="projects">
      <div className="space-y-8">
        <section className="text-center max-w-2xl mx-auto pt-2 sm:pt-6">
          <h1 className="font-display text-3xl sm:text-5xl text-ink">{t('projects.hero')}</h1>
          <p className="text-muted mt-2">{t('projects.hero.sub')}</p>
          <form onSubmit={startFromLink} className="mt-6 flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Link2 size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
              <input ref={linkRef} className="input-field pl-11 !py-3.5 !rounded-full shadow-card" type="url" value={link} onChange={(e) => setLink(e.target.value)}
                placeholder={t('projects.paste')} aria-label={t('projects.paste')} />
            </div>
            <button type="submit" disabled={!link.trim()} className="btn-primary px-6 py-3.5">
              {t('projects.go')} <ArrowRight size={16} />
            </button>
          </form>
          <button type="button" onClick={() => fileRef.current?.click()}
            className="mt-3 inline-flex items-center gap-2 text-sm text-muted hover:text-ink transition-colors">
            <Upload size={15} /> {t('projects.upload')}
          </button>
          <input ref={fileRef} type="file" accept="video/*,.mkv,.mov,.mp4,.webm" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) setCreating({ file: f }); }} />
        </section>

        <OnboardingChecklist refreshKey={total} firstProjectId={items?.[0]?.job_id} onCreateClip={focusLink} />

        <section>
          <div className="flex flex-col md:flex-row md:items-center gap-3 mb-5">
            <h2 className="font-display text-xl text-ink md:mr-auto">
              {t('projects.title')} {items && <span className="text-muted text-base">({total})</span>}
            </h2>
            <div className="relative md:w-64">
              <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
              <input className="input-field pl-10 !py-2.5" value={q} onChange={(e) => setQ(e.target.value)}
                placeholder={t('projects.search')} aria-label={t('projects.search')} />
            </div>
            <select className="input-field md:w-44 !py-2.5" value={sort} onChange={(e) => setSort(e.target.value)} aria-label={t('projects.sort')}>
              {SORTS.map((s) => <option key={s} value={s}>{t(`projects.sort.${s}`)}</option>)}
            </select>
            <div className="hidden sm:inline-flex rounded-full border border-rule-2 p-0.5 bg-paper2" role="group">
              {[['grid', LayoutGrid], ['list', List]].map(([id, Glyph]) => { const Icon = Glyph; return (
                <button key={id} type="button" onClick={() => pickView(id)} aria-pressed={view === id} aria-label={t(`projects.view.${id}`)} title={t(`projects.view.${id}`)}
                  className={`p-2 rounded-full transition-colors ${view === id ? 'bg-paper text-brass shadow-card' : 'text-muted hover:text-ink'}`}>
                  <Icon size={16} />
                </button>
              ); })}
            </div>
          </div>
          <Tabs className="mb-4" value={status} onChange={setStatus}
            tabs={FILTERS.map((f) => ({ id: f, label: t(`projects.filter.${f || 'all'}`) }))} />

          {collections.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mb-6" role="group" aria-label={t('collections.title')}>
              <button type="button" className="chip" aria-pressed={collection === null} onClick={() => setCollection(null)}>
                {t('collections.all')}
              </button>
              {collections.map((c) => (
                <span key={c.id} className={`chip !pr-1.5 ${collection === c.id ? 'is-active' : ''}`}>
                  <button type="button" className="inline-flex items-center gap-1.5" aria-pressed={collection === c.id} onClick={() => setCollection(c.id)}>
                    <Folder size={13} /> {c.name} <span className="readout !normal-case">{c.count}</span>
                  </button>
                  <button type="button" onClick={() => removeCollection(c)} aria-label={`${t('collections.delete')}: ${c.name}`}
                    className="p-1 rounded-full text-muted hover:text-danger"><X size={12} /></button>
                </span>
              ))}
            </div>
          )}

          {loadError && (
            <div className="card p-6 text-center text-sm text-muted">
              {t('projects.error')}{' '}
              <button type="button" className="underline text-ink" onClick={() => load()}>{t('common.retry')}</button>
            </div>
          )}
          {!loadError && items === null && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5" aria-busy="true">
              {[0, 1, 2].map((i) => <div key={i} className="card aspect-[4/3] skeleton" />)}
            </div>
          )}
          {empty && filtering && (
            <EmptyState compact icon={<Film size={22} />} title={t('projects.none.filtered')} />
          )}
          {empty && !filtering && (
            <div className="space-y-6">
              <EmptyState icon={<Clapperboard size={22} />} title={t('projects.empty')} text={t('projects.empty.sub')}
                action={<button type="button" className="btn-primary mt-1" onClick={() => fileRef.current?.click()}><Upload size={15} /> {t('projects.upload')}</button>} />
              <div>
                <h3 className="eyebrow mb-3">{t('projects.steps.title')}</h3>
                <div className="grid sm:grid-cols-3 gap-4">
                  {[[Link2, 1], [Wand2, 2], [Send, 3]].map(([Glyph, n]) => { const Icon = Glyph; return (
                    <div key={n} className="card p-5">
                      <span className="w-9 h-9 rounded-xl bg-brass/10 text-brass flex items-center justify-center mb-3"><Icon size={17} /></span>
                      <p className="text-sm font-semibold text-ink">{n}. {t(`projects.steps.${n}.t`)}</p>
                      <p className="text-sm text-muted mt-1">{t(`projects.steps.${n}.d`)}</p>
                    </div>
                  ); })}
                </div>
              </div>
            </div>
          )}
          {items && items.length > 0 && (
            <div className={view === 'list' ? 'space-y-3' : 'grid sm:grid-cols-2 lg:grid-cols-3 gap-5'}>
              {items.map((p) => (
                <ProjectCard key={p.job_id} project={p} view={view}
                  onRename={(proj) => { setRenaming(proj); setRenameTo(proj.title); }}
                  onDelete={setDeleting} onFavorite={toggleFavorite} onCollect={openCollect} />
              ))}
            </div>
          )}
        </section>
      </div>

      {dragging && (
        <div className="fixed inset-0 z-50 bg-paper/80 backdrop-blur-sm flex items-center justify-center pointer-events-none" aria-hidden="true">
          <div className="empty-state !border-brass !bg-paper shadow-pop px-16 py-16">
            <Upload size={34} className="text-brass" />
            <p className="font-display text-2xl text-ink">{t('projects.drop')}</p>
          </div>
        </div>
      )}

      <CreateProjectModal isOpen={!!creating} onClose={() => { setCreating(null); setLink(''); }}
        initialUrl={creating?.url || ''} initialFile={creating?.file || null} />

      <Modal isOpen={!!renaming} onClose={() => setRenaming(null)} size="sm" title={t('projects.rename')}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-quiet px-4 py-2" onClick={() => setRenaming(null)}>{t('common.cancel')}</button>
            <button type="button" className="btn-primary px-5 py-2" disabled={busy || !renameTo.trim()} onClick={confirmRename}>{t('common.save')}</button>
          </div>
        )}>
        <input className="input-field" value={renameTo} maxLength={200} autoFocus
          onChange={(e) => setRenameTo(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') confirmRename(); }} />
      </Modal>

      <Modal isOpen={!!collecting} onClose={() => setCollecting(null)} size="sm" title={t('collections.add.title')}>
        <div className="space-y-3">
          {collections.length === 0 && <p className="text-sm text-muted">{t('collections.none')}</p>}
          <ul className="space-y-1.5 max-h-64 overflow-y-auto custom-scrollbar">
            {collections.map((c) => (
              <li key={c.id}>
                <label className="flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-paper2 cursor-pointer text-sm text-ink2">
                  <input type="checkbox" className="w-4 h-4 accent-brass" checked={memberOf.includes(c.id)} onChange={() => toggleMember(c)} />
                  <Folder size={14} className="text-muted" /> <span className="flex-1 truncate">{c.name}</span>
                </label>
              </li>
            ))}
          </ul>
          <form className="flex gap-2 pt-2 border-t border-rule" onSubmit={(e) => { e.preventDefault(); createCollection(); }}>
            <input className="input-field !py-2.5" value={newName} maxLength={60} onChange={(e) => setNewName(e.target.value)}
              placeholder={t('collections.name')} aria-label={t('collections.name')} />
            <button type="submit" className="btn-primary !px-4 shrink-0" disabled={!newName.trim()}><Plus size={15} /> {t('collections.create')}</button>
          </form>
          {collError && <p className="text-sm text-danger" role="alert">{collError}</p>}
        </div>
      </Modal>

      <Modal isOpen={!!deleting} onClose={() => setDeleting(null)} size="sm" title={t('projects.delete.title')}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-quiet px-4 py-2" onClick={() => setDeleting(null)}>{t('common.cancel')}</button>
            <button type="button" className="btn-danger px-5 py-2" disabled={busy} onClick={confirmDelete}>{t('projects.delete')}</button>
          </div>
        )}>
        <p className="text-sm text-ink2">{t('projects.delete.body', { title: deleting?.title || '' })}</p>
      </Modal>
    </StudioShell>
  );
}
