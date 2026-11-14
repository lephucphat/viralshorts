import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, Upload, Trash2, Star, Loader2, Check, ImageOff } from 'lucide-react';
import StudioShell from '../StudioShell';
import Modal from '../components/ui/Modal';
import SegmentedControl from '../components/ui/SegmentedControl';
import { useLang } from '../contexts/LangContext';
import { kitsApi } from '../lib/studio';
import { getApiUrl } from '../config';

// Mirrors the presets in caption_presets.py / SubtitleModal.jsx.
const PRESETS = {
  classic: '#FFD700', tiktok: '#FE2C55', reels: '#E1306C', shorts: '#FF0000', gold: '#FFD700',
  neon: '#00FF88', cyber: '#00FFFF', karaoke: '#FF6B6B', minimal: '#FFFFFF', beast: '#FFD700', boxed: '#7C3AED',
};
const POSITIONS = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
const HOOK_STYLES = ['classic', 'dark', 'yellow', 'red', 'outline', 'outline_yellow'];
const LAYOUTS = ['auto', 'split', 'screencast', 'none'];
const FORMATS = ['vertical', 'square', 'horizontal'];
const EDITABLE = ['name', 'logo_position', 'logo_opacity', 'logo_scale', 'primary_color', 'secondary_color',
  'caption_preset', 'hook_style', 'layout', 'output_format'];

const CORNER = {
  'top-left': 'top-[4%] left-[6%]', 'top-right': 'top-[4%] right-[6%]',
  'bottom-left': 'bottom-[16%] left-[6%]', 'bottom-right': 'bottom-[16%] right-[6%]',
};

function Preview({ draft, t }) {
  const color = PRESETS[draft.caption_preset] || PRESETS.classic;
  const boxed = draft.caption_preset === 'boxed';
  const upper = draft.caption_preset === 'beast';
  return (
    <div className="mx-auto w-44 sm:w-52 aspect-[9/16] rounded-[22px] border border-rule2 overflow-hidden relative"
      style={{ background: `linear-gradient(160deg, ${draft.primary_color}, ${draft.secondary_color})` }}
      aria-label={t('brand.preview')} role="img">
      {draft.logo_url ? (
        <img src={getApiUrl(draft.logo_url)} alt="" className={`absolute ${CORNER[draft.logo_position] || CORNER['top-right']} object-contain`}
          style={{ width: `${draft.logo_scale * 100}%`, opacity: draft.logo_opacity }} />
      ) : (
        <span className={`absolute ${CORNER[draft.logo_position] || CORNER['top-right']} text-[0.625rem] text-white/70 border border-dashed border-white/50 rounded px-1.5 py-0.5`}>
          logo
        </span>
      )}
      <div className="absolute inset-x-3 bottom-[34%] text-center">
        <span className={`inline-block text-[0.8125rem] font-extrabold leading-tight px-1.5 py-0.5 ${boxed ? 'rounded' : ''}`}
          style={{ color: '#fff', textTransform: upper ? 'uppercase' : 'none', textShadow: '0 1px 3px rgba(0,0,0,.8)', background: boxed ? color : 'transparent' }}>
          {t('brand.preview.line')} <span style={{ color: boxed ? '#fff' : color }}>{t('brand.preview.word')}</span>
        </span>
      </div>
    </div>
  );
}

function Slider({ label, value, min, max, step, onChange, format }) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between">
        <span className="eyebrow">{label}</span>
        <span className="readout">{format(value)}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full mt-2 accent-[color:var(--color-brass)]" />
    </label>
  );
}

export default function BrandPage() {
  const { t } = useLang();
  const [kits, setKits] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);

  const selected = useMemo(() => (kits || []).find((k) => k.id === selectedId) || null, [kits, selectedId]);

  const load = useCallback(async (focusId) => {
    try {
      const { items } = await kitsApi.list();
      setKits(items);
      setSelectedId((cur) => focusId ?? (items.some((k) => k.id === cur) ? cur : (items[0]?.id ?? null)));
    } catch (e) { setError(e.message); setKits([]); }
  }, []);
  useEffect(() => { load(); }, [load]);

  // Local edits live only in the draft. Switching kit replaces it; a reload of
  // the same kit (after a logo upload, say) refreshes only what the server owns,
  // so unsaved edits to the name or colours survive.
  useEffect(() => {
    setDraft(selected ? { ...selected } : null); setSaved(false); setError('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);
  useEffect(() => {
    if (!selected) return;
    setDraft((d) => (d && d.id === selected.id
      ? { ...d, logo_url: selected.logo_url, has_logo: selected.has_logo, is_default: selected.is_default }
      : d));
  }, [selected]);

  const dirty = !!(draft && selected && EDITABLE.some((k) => draft[k] !== selected[k]));
  const set = (patch) => { setDraft((d) => ({ ...d, ...patch })); setSaved(false); };

  const createKit = async () => {
    setError('');
    try {
      const kit = await kitsApi.create({ name: t('brand.new.name', { n: (kits?.length || 0) + 1 }) });
      await load(kit.id);
    } catch (e) { setError(e.message); }
  };

  const save = async () => {
    setSaving(true); setError('');
    try {
      const fields = Object.fromEntries(EDITABLE.filter((k) => draft[k] !== selected[k]).map((k) => [k, draft[k]]));
      await kitsApi.update(selected.id, fields);
      await load(selected.id);
      setSaved(true);
    } catch (e) { setError(e.message); } finally { setSaving(false); }
  };

  const makeDefault = async () => {
    try { await kitsApi.update(selected.id, { is_default: true }); await load(selected.id); }
    catch (e) { setError(e.message); }
  };

  const remove = async () => {
    try { await kitsApi.remove(selected.id); setConfirmDelete(false); await load(); }
    catch (e) { setError(e.message); }
  };

  const onLogo = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setLogoBusy(true); setError('');
    try { await kitsApi.uploadLogo(selected.id, file); await load(selected.id); }
    catch (err) { setError(err.message); } finally { setLogoBusy(false); }
  };
  const dropLogo = async () => {
    setLogoBusy(true);
    try { await kitsApi.removeLogo(selected.id); await load(selected.id); }
    catch (err) { setError(err.message); } finally { setLogoBusy(false); }
  };

  return (
    <StudioShell active="brand">
      <div className="flex items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display text-3xl text-ink">{t('brand.title')}</h1>
          <p className="text-muted mt-1.5 max-w-xl">{t('brand.sub')}</p>
        </div>
        <button type="button" className="btn-primary px-4 py-2.5 shrink-0" onClick={createKit}>
          <Plus size={16} /> {t('brand.new')}
        </button>
      </div>

      {kits === null && <div className="card h-64 animate-pulse bg-paper3" aria-busy="true" />}
      {kits && kits.length === 0 && (
        <div className="card p-10 text-center">
          <ImageOff size={30} className="mx-auto text-muted mb-3" />
          <p className="text-ink font-medium">{t('brand.empty')}</p>
          <p className="text-sm text-muted mt-1 mb-5">{t('brand.empty.sub')}</p>
          <button type="button" className="btn-primary px-5 py-2.5" onClick={createKit}>{t('brand.new')}</button>
        </div>
      )}

      {kits && kits.length > 0 && draft && (
        <div className="grid lg:grid-cols-[14rem_1fr_16rem] gap-6 items-start">
          <nav className="card p-2 flex lg:flex-col gap-1 overflow-x-auto" aria-label={t('brand.title')}>
            {kits.map((k) => (
              <button key={k.id} type="button" onClick={() => setSelectedId(k.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-input text-sm text-left whitespace-nowrap lg:whitespace-normal ${k.id === selectedId ? 'bg-paper3 text-ink font-medium' : 'text-muted hover:text-ink hover:bg-paper3/60'}`}>
                <span className="truncate flex-1">{k.name}</span>
                {k.is_default && <Star size={13} className="text-brass shrink-0" aria-label={t('brand.default')} />}
              </button>
            ))}
          </nav>

          <section className="card p-5 sm:p-6 space-y-6">
            <label className="block">
              <span className="eyebrow">{t('brand.name')}</span>
              <input className="input-field mt-1.5" value={draft.name} maxLength={60} onChange={(e) => set({ name: e.target.value })} />
            </label>

            <div>
              <span className="eyebrow">{t('brand.logo')}</span>
              <div className="mt-2 flex items-center gap-4">
                <div className="w-20 h-20 rounded-card border border-rule bg-paper3 flex items-center justify-center overflow-hidden shrink-0">
                  {selected?.logo_url
                    ? <img src={getApiUrl(selected.logo_url)} alt="" className="max-w-full max-h-full object-contain" />
                    : <ImageOff size={22} className="text-muted" />}
                </div>
                <div className="space-y-2">
                  <label className="btn-ghost px-4 py-2 text-sm cursor-pointer inline-flex">
                    {logoBusy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />}
                    {selected?.has_logo ? t('brand.logo.replace') : t('brand.logo.upload')}
                    <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={onLogo} disabled={logoBusy} />
                  </label>
                  {selected?.has_logo && (
                    <button type="button" className="block text-xs text-muted hover:text-danger" onClick={dropLogo}>{t('brand.logo.remove')}</button>
                  )}
                  <p className="text-xs text-muted">{t('brand.logo.hint')}</p>
                </div>
              </div>
            </div>

            <div className="grid sm:grid-cols-2 gap-5">
              <div>
                <span className="eyebrow">{t('brand.position')}</span>
                <div className="mt-1.5">
                  <SegmentedControl columns={2} size="sm" value={draft.logo_position} onChange={(v) => set({ logo_position: v })}
                    options={POSITIONS.map((p) => ({ value: p, label: t(`brand.pos.${p}`) }))} />
                </div>
              </div>
              <div className="space-y-4">
                <Slider label={t('brand.opacity')} value={draft.logo_opacity} min={0.1} max={1} step={0.05}
                  format={(v) => `${Math.round(v * 100)}%`} onChange={(v) => set({ logo_opacity: v })} />
                <Slider label={t('brand.size')} value={draft.logo_scale} min={0.05} max={0.4} step={0.01}
                  format={(v) => `${Math.round(v * 100)}%`} onChange={(v) => set({ logo_scale: v })} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-5">
              {[['primary_color', 'brand.color.primary'], ['secondary_color', 'brand.color.secondary']].map(([key, label]) => (
                <label key={key} className="block">
                  <span className="eyebrow">{t(label)}</span>
                  <span className="mt-1.5 flex items-center gap-3">
                    <input type="color" value={draft[key]} onChange={(e) => set({ [key]: e.target.value.toUpperCase() })}
                      className="w-11 h-11 rounded-input border border-rule2 bg-transparent cursor-pointer p-1" />
                    <span className="readout">{draft[key]}</span>
                  </span>
                </label>
              ))}
            </div>

            <div>
              <span className="eyebrow">{t('brand.captions')}</span>
              <div className="mt-2 grid grid-cols-3 sm:grid-cols-4 gap-2">
                {Object.entries(PRESETS).map(([id, color]) => (
                  <button key={id} type="button" onClick={() => set({ caption_preset: id })} aria-pressed={draft.caption_preset === id}
                    className={`px-2 py-2 rounded-input border text-xs flex items-center justify-center gap-1.5 transition-colors ${draft.caption_preset === id ? 'border-brass text-ink bg-paper3' : 'border-rule2 text-muted hover:border-brass'}`}>
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                    {t(`brand.preset.${id}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid sm:grid-cols-3 gap-4">
              <label className="block">
                <span className="eyebrow">{t('brand.hook')}</span>
                <select className="input-field mt-1.5" value={draft.hook_style} onChange={(e) => set({ hook_style: e.target.value })}>
                  {HOOK_STYLES.map((s) => <option key={s} value={s}>{t(`hook.style.${s}`)}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="eyebrow">{t('create.layout')}</span>
                <select className="input-field mt-1.5" value={draft.layout} onChange={(e) => set({ layout: e.target.value })}>
                  {LAYOUTS.map((l) => <option key={l} value={l}>{t(`create.layout.${l}`)}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="eyebrow">{t('create.format')}</span>
                <select className="input-field mt-1.5" value={draft.output_format} onChange={(e) => set({ output_format: e.target.value })}>
                  {FORMATS.map((f) => <option key={f} value={f}>{t(`create.format.${f}`)}</option>)}
                </select>
              </label>
            </div>

            {error && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">{error}</p>}

            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-rule">
              <button type="button" className="btn-primary px-6 py-2.5" disabled={!dirty || saving || !draft.name.trim()} onClick={save}>
                {saving ? <Loader2 size={16} className="animate-spin" /> : saved ? <Check size={16} /> : null}
                {saved && !dirty ? t('common.saved') : t('common.save')}
              </button>
              {!selected.is_default && (
                <button type="button" className="btn-ghost px-4 py-2.5" onClick={makeDefault}>
                  <Star size={15} /> {t('brand.makedefault')}
                </button>
              )}
              <button type="button" className="btn-quiet px-4 py-2.5 ml-auto text-danger" onClick={() => setConfirmDelete(true)}>
                <Trash2 size={15} /> {t('projects.delete')}
              </button>
            </div>
          </section>

          <aside className="lg:sticky lg:top-6">
            <p className="eyebrow text-center mb-3">{t('brand.preview')}</p>
            <Preview draft={draft} t={t} />
          </aside>
        </div>
      )}

      <Modal isOpen={confirmDelete} onClose={() => setConfirmDelete(false)} size="sm" title={t('brand.delete.title')}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-quiet px-4 py-2" onClick={() => setConfirmDelete(false)}>{t('common.cancel')}</button>
            <button type="button" className="btn-danger px-5 py-2" onClick={remove}>{t('projects.delete')}</button>
          </div>
        )}>
        <p className="text-sm text-ink2">{t('brand.delete.body', { name: selected?.name || '' })}</p>
      </Modal>
    </StudioShell>
  );
}
