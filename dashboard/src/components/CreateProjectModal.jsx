import { useEffect, useRef, useState } from 'react';
import { Link2, Upload, FileVideo, X, ChevronDown, Loader2, AlertTriangle } from 'lucide-react';
import Modal from './ui/Modal';
import SegmentedControl from './ui/SegmentedControl';
import { useLang } from '../contexts/LangContext';
import CreditNote from './CreditNote';
import { kitsApi, recipesApi, sourceApi, createProject, QuotaError, formatDuration } from '../lib/studio';

const GENRES = ['podcast', 'interview', 'vlog', 'tutorial', 'gaming', 'sports', 'education', 'business', 'other'];
const LANGUAGES = ['auto', 'vi', 'en', 'ja', 'ko', 'zh', 'es', 'fr', 'de', 'pt', 'id', 'th', 'ru', 'hi'];
const LENGTHS = ['', 'short', 'medium', 'long'];
const FORMATS = ['', 'vertical', 'square', 'horizontal'];
const LAYOUTS = ['', 'auto', 'split', 'screencast', 'none'];
const REMEMBER = 'vs_create_prefs';

function readPrefs() {
  try { return JSON.parse(localStorage.getItem(REMEMBER) || '{}'); } catch (_) { return {}; }
}

function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="eyebrow">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="text-xs text-muted mt-1.5 block">{hint}</span>}
    </label>
  );
}

// The "new project" dialog: the source plus the controls OpusClip puts on its
// own create screen. Everything optional is sent only when set, so a project
// made with the defaults is the same request the API has always accepted.
export default function CreateProjectModal({ isOpen, onClose, initialUrl = '', initialFile = null }) {
  const { t } = useLang();
  const prefs = useRef(readPrefs()).current;
  const [mode, setMode] = useState('url');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [kits, setKits] = useState([]);
  const [kitId, setKitId] = useState('');          // '' = the account default, 'none' = no branding
  const [genre, setGenre] = useState(prefs.genre || '');
  const [keywords, setKeywords] = useState('');
  const [clipLength, setClipLength] = useState(prefs.clipLength || '');
  const [language, setLanguage] = useState(prefs.language || 'auto');
  const [showRange, setShowRange] = useState(false);
  const [timeStart, setTimeStart] = useState('');
  const [timeEnd, setTimeEnd] = useState('');
  const [targetClips, setTargetClips] = useState('');
  const [outputFormat, setOutputFormat] = useState('');
  const [layout, setLayout] = useState('');
  const [captions, setCaptions] = useState(prefs.captions !== false);
  const [autoHook, setAutoHook] = useState(prefs.autoHook !== false);
  const [showMore, setShowMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [quotaHit, setQuotaHit] = useState(false);   // show the "top up or upgrade" link
  const [lowQuality, setLowQuality] = useState(null);

  useEffect(() => {
    if (!isOpen) return;
    setError(''); setLowQuality(null); setBusy(false);
    if (initialFile) { setMode('file'); setFile(initialFile); setUrl(''); }
    else if (initialUrl) { setMode('url'); setUrl(initialUrl); setFile(null); }
    kitsApi.list().then((r) => setKits(r.items || [])).catch(() => setKits([]));
  }, [isOpen, initialUrl, initialFile]);

  // Source preview: once a link looks complete, read its title/cover/length (no credit is spent).
  const [preview, setPreview] = useState(null);       // null | {loading} | {error} | {data}
  useEffect(() => {
    const link = url.trim();
    if (!isOpen || mode !== 'url' || !/^https?:\/\/\S+\.\S+/i.test(link)) { setPreview(null); return undefined; }
    let alive = true;
    setPreview({ loading: true });
    const timer = setTimeout(() => {
      sourceApi.preview(link)
        .then((data) => { if (alive) setPreview({ data }); })
        .catch(() => { if (alive) setPreview({ error: true }); });
    }, 600);
    return () => { alive = false; clearTimeout(timer); };
  }, [url, mode, isOpen]);

  // Recipes: saved sets of the settings below, re-applied with one click.
  const [recipes, setRecipes] = useState([]);
  const [recipeNote, setRecipeNote] = useState('');
  const [savingRecipe, setSavingRecipe] = useState(false);
  const [recipeName, setRecipeName] = useState('');
  useEffect(() => {
    if (!isOpen) return;
    recipesApi.list().then((r) => setRecipes(r.items || [])).catch(() => setRecipes([]));
  }, [isOpen]);

  const currentSettings = () => ({
    genre, language, clipLength, keywords: keywords.trim(), targetClips, outputFormat, layout, kitId, captions, autoHook,
  });
  const applyRecipe = (recipe) => {
    const s = recipe.settings || {};
    if ('genre' in s) setGenre(s.genre);
    if ('language' in s) setLanguage(s.language || 'auto');
    if ('clipLength' in s) setClipLength(s.clipLength);
    if ('keywords' in s) setKeywords(s.keywords);
    if ('targetClips' in s) setTargetClips(s.targetClips);
    if ('outputFormat' in s) setOutputFormat(s.outputFormat);
    if ('layout' in s) setLayout(s.layout);
    if ('kitId' in s) setKitId(s.kitId === '' || s.kitId === 'none' || kits.some((k) => String(k.id) === s.kitId) ? s.kitId : '');
    if ('captions' in s) setCaptions(s.captions);
    if ('autoHook' in s) setAutoHook(s.autoHook);
    setRecipeNote(t('recipes.applied', { name: recipe.name }));
  };
  const saveRecipe = async () => {
    const name = recipeName.trim();
    if (!name) return;
    try {
      const made = await recipesApi.create(name, currentSettings());
      setRecipes((list) => [...list, made].sort((a, b) => a.name.localeCompare(b.name)));
      setSavingRecipe(false); setRecipeName(''); setRecipeNote('');
    } catch (e) {
      setRecipeNote(e.code === 'exists' ? t('recipes.err.exists')
        : e.code === 'too_many' ? t('recipes.err.too_many') : t('recipes.err.generic'));
    }
  };
  const removeRecipe = async (recipe) => {
    try {
      await recipesApi.remove(recipe.id);
      setRecipes((list) => list.filter((r) => r.id !== recipe.id));
    } catch (_) { /* leave it listed */ }
  };

  const defaultKit = kits.find((k) => k.is_default);
  const hasSource = mode === 'url' ? url.trim().length > 0 : !!file;
  const ready = hasSource && !busy;

  const submit = async (force = false) => {
    if (!ready && !force) return;
    setBusy(true); setError(''); setLowQuality(null);
    const options = {
      brand_kit_id: kitId,
      genre: genre === 'other' ? '' : genre,
      keywords: keywords.trim(),
      clip_length: clipLength,
      time_start: showRange ? timeStart.trim() : '',
      time_end: showRange ? timeEnd.trim() : '',
      source_language: language === 'auto' ? '' : language,
      target_clips: targetClips,
      output_format: outputFormat,
      layouts: layout,
      captions: captions ? '' : 'false',
      auto_hook: autoHook ? '1' : '0',
    };
    try {
      const source = mode === 'url' ? { kind: 'url', url: url.trim() } : { kind: 'file', file };
      const res = await createProject(source, options, { forceLowQuality: force });
      if (res.needs_confirmation) {
        setLowQuality(res.quality_check || {});
        setBusy(false);
        return;
      }
      try {
        localStorage.setItem(REMEMBER, JSON.stringify({ genre, clipLength, language, captions, autoHook }));
      } catch (_) { /* best effort */ }
      onClose();
      window.location.hash = `#/project/${res.job_id}`;
    } catch (e) {
      setQuotaHit(e instanceof QuotaError);
      if (e instanceof QuotaError && e.needsPlan) setError(t('billing.plan_required'));
      else if (e instanceof QuotaError && e.creditsRequired != null) {
        setError(t('billing.quota.body', { required: e.creditsRequired, remaining: e.creditsRemaining ?? 0 }));
      } else if (e instanceof QuotaError) setError(t('create.err.quota'));
      else if (e.code === 'too_many_jobs') setError(t('create.err.busy'));
      else if (e.code === 'quota_exceeded') setError(t('create.err.quota'));
      else setError(e.message || t('create.err.generic'));
      setBusy(false);
    }
  };

  const tab = (id, Icon, label) => (
    <button type="button" onClick={() => setMode(id)}
      className={`flex items-center gap-2 pb-3 px-1 -mb-px border-b-2 text-sm whitespace-nowrap transition-colors ${mode === id ? 'text-ink border-brass' : 'text-muted border-transparent hover:text-ink2'}`}>
      <Icon size={16} className={mode === id ? 'text-brass' : ''} /> {label}
    </button>
  );

  const select = (value, onChange, options, labelFor) => (
    <select className="input-field" value={value} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => <option key={o} value={o}>{labelFor(o)}</option>)}
    </select>
  );

  return (
    <Modal isOpen={isOpen} onClose={busy ? undefined : onClose} size="lg" title={t('create.title')}
      footer={(
        <div className="space-y-3">
          <p className="text-xs text-muted leading-relaxed">{t('create.rights')}</p>
          <div className="flex items-center justify-end gap-2">
            <CreditNote cost="process_per_minute" perMinute className="text-xs text-muted mr-auto" />
            <button type="button" className="btn-quiet px-4 py-2" onClick={onClose} disabled={busy}>{t('common.cancel')}</button>
            <button type="button" className="btn-primary px-5 py-2" disabled={!ready} onClick={() => submit()}>
              {busy && <Loader2 size={16} className="animate-spin" />}
              {busy ? (mode === 'file' ? t('create.uploading') : t('create.starting')) : t('create.cta')}
            </button>
          </div>
        </div>
      )}>
      <div className="space-y-5">
        <div className="flex gap-6 border-b border-rule">
          {tab('url', Link2, t('create.tab.url'))}
          {tab('file', Upload, t('create.tab.file'))}
        </div>

        {mode === 'url' ? (
          <div className="space-y-3">
            <input className="input-field" type="url" value={url} onChange={(e) => setUrl(e.target.value)}
              placeholder={t('create.url.placeholder')} aria-label={t('create.tab.url')} autoFocus />
            {preview?.loading && (
              <div className="card flex gap-3 p-3" aria-live="polite">
                <div className="skeleton w-28 aspect-video rounded-input shrink-0" />
                <div className="flex-1 space-y-2 py-1">
                  <div className="skeleton h-4 w-3/4 rounded" />
                  <div className="skeleton h-3 w-1/3 rounded" />
                  <span className="sr-only">{t('create.preview.loading')}</span>
                </div>
              </div>
            )}
            {preview?.error && <p className="text-xs text-muted">{t('create.preview.fail')}</p>}
            {preview?.data && (
              <div className="card flex gap-3 p-3 animate-fade">
                <div className="relative w-28 shrink-0 aspect-video rounded-input overflow-hidden bg-paper3">
                  {preview.data.thumbnail && (
                    <img src={preview.data.thumbnail} alt="" referrerPolicy="no-referrer" loading="lazy"
                      className="w-full h-full object-cover" />
                  )}
                  {preview.data.duration > 0 && (
                    <span className="absolute bottom-1 right-1 rounded bg-black/75 text-white text-[0.6875rem] px-1.5 py-0.5 tabular-nums">
                      {formatDuration(preview.data.duration)}
                    </span>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink line-clamp-2">{preview.data.title}</p>
                  {preview.data.channel && <p className="text-xs text-muted mt-0.5 truncate">{preview.data.channel}</p>}
                  {preview.data.duration > 0 && (
                    <p className="text-xs text-brass mt-1 font-medium">
                      {t('create.preview.credits', { n: Math.max(1, Math.ceil(preview.data.duration / 60)) })}
                    </p>
                  )}
                  {preview.data.live && <p className="text-xs text-warn mt-1">{t('create.preview.live')}</p>}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className={`border-2 border-dashed rounded-card p-6 text-center ${file ? 'border-brass' : 'border-rule2'}`}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]); }}>
            {file ? (
              <div className="flex items-center justify-center gap-3 min-w-0">
                <FileVideo size={18} className="shrink-0 text-ok" />
                <span className="font-medium text-ink truncate">{file.name}</span>
                <button type="button" onClick={() => setFile(null)} aria-label={t('common.remove')}
                  className="p-1 rounded-full text-muted hover:text-ink hover:bg-paper3"><X size={16} /></button>
              </div>
            ) : (
              <label className="cursor-pointer block">
                <input type="file" accept="video/*,.mkv,.mov,.mp4,.webm" className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)} />
                <Upload size={22} className="mx-auto text-muted mb-2" />
                <span className="text-sm text-ink2">{t('create.file.drop')}</span>
                <span className="block text-xs text-muted mt-1">{t('create.file.hint')}</span>
              </label>
            )}
          </div>
        )}

        <div>
          <span className="eyebrow">{t('recipes.title')}</span>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {recipes.map((r) => (
              <span key={r.id} className="inline-flex items-center rounded-full border border-rule bg-paper2 text-sm text-ink2">
                <button type="button" className="pl-3 pr-1.5 py-1 hover:text-ink" onClick={() => applyRecipe(r)}>{r.name}</button>
                <button type="button" aria-label={t('recipes.remove', { name: r.name })}
                  className="pr-2 pl-0.5 py-1 text-muted hover:text-danger" onClick={() => removeRecipe(r)}>
                  <X size={13} />
                </button>
              </span>
            ))}
            {savingRecipe ? (
              <span className="inline-flex items-center gap-2">
                <input className="input-field !py-1 !text-sm w-52" value={recipeName} maxLength={40} autoFocus
                  placeholder={t('recipes.name')} aria-label={t('recipes.name')}
                  onChange={(e) => setRecipeName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveRecipe(); } if (e.key === 'Escape') setSavingRecipe(false); }} />
                <button type="button" className="btn-secondary px-3 py-1 text-sm" disabled={!recipeName.trim()} onClick={saveRecipe}>
                  {t('recipes.ok')}
                </button>
              </span>
            ) : (
              <button type="button" className="chip" onClick={() => { setSavingRecipe(true); setRecipeNote(''); }}>
                {t('recipes.save')}
              </button>
            )}
          </div>
          {recipeNote && <p className="text-xs text-muted mt-1.5" role="status">{recipeNote}</p>}
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <Field label={t('create.genre')}>
            <select className="input-field" value={genre} onChange={(e) => setGenre(e.target.value)}>
              <option value="">{t('create.genre.auto')}</option>
              {GENRES.map((g) => <option key={g} value={g}>{t(`genre.${g}`)}</option>)}
            </select>
          </Field>
          <Field label={t('create.language')}>
            {select(language, setLanguage, LANGUAGES, (l) => (l === 'auto' ? t('create.language.auto') : t(`lng.${l}`)))}
          </Field>
        </div>

        <Field label={t('create.keywords')} hint={t('create.keywords.hint')}>
          <input className="input-field" value={keywords} maxLength={200}
            onChange={(e) => setKeywords(e.target.value)} placeholder={t('create.keywords.placeholder')} />
        </Field>

        <div>
          <span className="eyebrow">{t('create.length')}</span>
          <div className="mt-1.5">
            <SegmentedControl value={clipLength} onChange={setClipLength}
              options={LENGTHS.map((l) => ({ value: l, label: t(`create.length.${l || 'auto'}`) }))} />
          </div>
        </div>

        <Field label={t('create.brand')} hint={kits.length === 0 ? t('create.brand.none.hint') : undefined}>
          <select className="input-field" value={kitId} onChange={(e) => setKitId(e.target.value)} disabled={kits.length === 0}>
            <option value="">
              {defaultKit ? t('create.brand.default', { name: defaultKit.name }) : t('create.brand.nokit')}
            </option>
            {kits.length > 0 && <option value="none">{t('create.brand.off')}</option>}
            {kits.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
        </Field>

        <div className="border-t border-rule pt-4">
          <button type="button" onClick={() => setShowMore((v) => !v)} aria-expanded={showMore}
            className="flex items-center gap-2 text-sm text-ink2 hover:text-ink">
            <ChevronDown size={16} className={`transition-transform ${showMore ? 'rotate-180' : ''}`} />
            {t('create.more')}
          </button>
          {showMore && (
            <div className="mt-4 space-y-4 animate-fade">
              <label className="flex items-center gap-2.5 text-sm text-ink2 cursor-pointer">
                <input type="checkbox" className="accent-[color:var(--color-brass)]" checked={showRange}
                  onChange={(e) => setShowRange(e.target.checked)} />
                {t('create.range')}
              </label>
              {showRange && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label={t('create.range.from')}>
                    <input className="input-field" value={timeStart} onChange={(e) => setTimeStart(e.target.value)} placeholder="0:00" inputMode="numeric" />
                  </Field>
                  <Field label={t('create.range.to')}>
                    <input className="input-field" value={timeEnd} onChange={(e) => setTimeEnd(e.target.value)} placeholder="10:00" inputMode="numeric" />
                  </Field>
                  <p className="col-span-2 text-xs text-muted">{t('create.range.hint')}</p>
                </div>
              )}
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label={t('create.count')} hint={t('create.count.hint')}>
                  <input className="input-field" type="number" min={1} max={15} value={targetClips}
                    onChange={(e) => setTargetClips(e.target.value)} placeholder={t('create.count.auto')} />
                </Field>
                <Field label={t('create.format')}>
                  {select(outputFormat, setOutputFormat, FORMATS, (f) => t(`create.format.${f || 'default'}`))}
                </Field>
                <Field label={t('create.layout')}>
                  {select(layout, setLayout, LAYOUTS, (l) => t(`create.layout.${l || 'default'}`))}
                </Field>
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-3">
                <label className="flex items-center gap-2.5 text-sm text-ink2 cursor-pointer">
                  <input type="checkbox" className="accent-[color:var(--color-brass)]" checked={captions}
                    onChange={(e) => setCaptions(e.target.checked)} />
                  {t('create.captions')}
                </label>
                <label className="flex items-center gap-2.5 text-sm text-ink2 cursor-pointer">
                  <input type="checkbox" className="accent-[color:var(--color-brass)]" checked={autoHook}
                    onChange={(e) => setAutoHook(e.target.checked)} />
                  {t('create.hook')}
                </label>
              </div>
            </div>
          )}
        </div>

        {lowQuality && (
          <div className="rounded-card border border-rule bg-paper3 p-4 space-y-3" role="alert">
            <p className="flex items-start gap-2 text-sm text-ink2">
              <AlertTriangle size={16} className="text-warn shrink-0 mt-0.5" />
              {t('create.lowq', { have: lowQuality.max_height || '?', want: lowQuality.min_height || '?' })}
            </p>
            <div className="flex gap-2 justify-end">
              <button type="button" className="btn-quiet px-3 py-1.5 text-xs" onClick={() => setLowQuality(null)}>{t('common.cancel')}</button>
              <button type="button" className="btn-primary px-3 py-1.5 text-xs" onClick={() => submit(true)}>{t('create.lowq.go')}</button>
            </div>
          </div>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">
            {error}
            {quotaHit && <> <a href="#/pricing" className="underline font-medium" onClick={onClose}>{t('billing.quota.cta')}</a></>}
          </p>
        )}
      </div>
    </Modal>
  );
}
