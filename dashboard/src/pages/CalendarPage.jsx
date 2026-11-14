import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CalendarDays, ChevronLeft, ChevronRight, Plus, Loader2, Film, Check, KeyRound, ExternalLink,
  Video, Instagram, Youtube, GripVertical,
} from 'lucide-react';
import StudioShell from '../StudioShell';
import Modal from '../components/ui/Modal';
import EmptyState from '../components/ui/EmptyState';
import SegmentedControl from '../components/ui/SegmentedControl';
import ScheduleWeekModal from '../components/ScheduleWeekModal';
import TikTokDraftNotice from '../components/TikTokDraftNotice';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';
import { apiFetch, QuotaError } from '../lib/api';
import { calendarApi, projectsApi } from '../lib/studio';
import {
  getUploadPostKey, setUploadPostKey, getUploadUserId, setUploadUserId,
} from '../lib/socialKey';

const PLATFORMS = [
  { value: 'tiktok', label: 'TikTok', icon: <Video size={16} /> },
  { value: 'instagram', label: 'Instagram', icon: <Instagram size={16} /> },
  { value: 'youtube', label: 'YouTube', icon: <Youtube size={16} /> },
];
const STATUS_TONE = {
  planned: 'badge-brass', scheduled: 'badge-ok', published: 'badge-ok', failed: 'badge-danger', cancelled: 'badge-warn',
};
const DOT_TONE = {
  planned: 'bg-brass', scheduled: 'bg-ok', published: 'bg-ok', failed: 'bg-danger', cancelled: 'bg-warn',
};
const EDITABLE = ['planned', 'failed'];
const DAY = 86400 * 1000;
const ERR_CODES = ['past_date', 'too_far', 'bad_platforms', 'locked', 'cancel_first', 'bad_transition', 'too_many', 'not_found'];

const pad = (n) => String(n).padStart(2, '0');
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const mondayOf = (d) => addDays(startOfDay(d), -((d.getDay() + 6) % 7));
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const hm = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
const fromParts = (dateStr, timeStr) => {
  const [y, m, d] = dateStr.split('-').map(Number);
  const [hh, mm] = (timeStr || '12:00').split(':').map(Number);
  return new Date(y, m - 1, d, hh, mm);
};
const browserTz = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { return 'UTC'; } };

// "2026-11-13T12:00:00" as the wall clock of `tz`, which is what Upload-Post wants next to the zone name.
function wallClock(epochSeconds, tz) {
  const when = new Date(epochSeconds * 1000);
  try {
    return when.toLocaleString('sv-SE', { timeZone: tz, hour12: false }).replace(' ', 'T');
  } catch (_) {
    return `${ymd(when)}T${hm(when)}:00`;
  }
}

function useErr(t) {
  return (e) => {
    if (e instanceof QuotaError) return t('err.plan_required');
    const code = e?.code;
    return ERR_CODES.includes(code) ? t(`cal.err.${code}`) : t('cal.err.generic');
  };
}

function clipView(clip, t, n) {
  return {
    title: clip?.video_title_for_youtube_short || clip?.title || t('cal.clip.fallback'),
    description: clip?.video_description_for_instagram || clip?.video_description_for_tiktok || '',
    n,
  };
}

// ---------------------------------------------------------------------------------------------
function PostModal({ state, onClose, projects, clipsByJob, ensureClips, onSaved, onSend, onCancelQueued, onDelete, canSend, busy }) {
  const { t } = useLang();
  const errText = useErr(t);
  const { post, draft: seed } = state;
  const editing = !!post;
  const locked = editing && !EDITABLE.includes(post.status);
  const [f, setF] = useState(() => {
    if (post) {
      const d = new Date(post.scheduled_for * 1000);
      return { jobId: post.job_id, clip: post.clip_index, date: ymd(d), time: hm(d), platforms: post.platforms,
        title: post.title, description: post.description };
    }
    return { jobId: seed.jobId || '', clip: seed.clip ?? '', date: seed.date, time: seed.time || '12:00',
      platforms: ['tiktok', 'instagram', 'youtube'], title: seed.title || '', description: seed.description || '' };
  });
  const [err, setErr] = useState('');
  const [saving, setSaving] = useState(false);
  const clips = clipsByJob[f.jobId];

  useEffect(() => { if (f.jobId && !editing) ensureClips(f.jobId); }, [f.jobId, editing, ensureClips]);

  const pickProject = (jobId) => setF((x) => ({ ...x, jobId, clip: '', title: '', description: '' }));
  const pickClip = (idx) => {
    const clip = clips?.[Number(idx)];
    const v = clipView(clip, t, Number(idx) + 1);
    setF((x) => ({ ...x, clip: idx, title: clip ? v.title : '', description: clip ? v.description : '' }));
  };

  const submit = async () => {
    setSaving(true); setErr('');
    try {
      const when = fromParts(f.date, f.time).getTime() / 1000;
      if (editing) {
        const saved = await calendarApi.update(post.id, { title: f.title, description: f.description,
          platforms: f.platforms, scheduled_for: when, timezone: browserTz() });
        onSaved(saved);
      } else {
        const saved = await calendarApi.create({ job_id: f.jobId, clip_index: Number(f.clip), title: f.title,
          description: f.description, platforms: f.platforms, scheduled_for: when, timezone: browserTz() });
        onSaved(saved);
      }
    } catch (e) { setErr(errText(e)); } finally { setSaving(false); }
  };

  const valid = f.jobId && f.clip !== '' && f.platforms.length > 0 && f.date;
  const status = post?.status;
  const footer = (
    <div className="flex flex-col-reverse sm:flex-row sm:flex-wrap gap-2 sm:justify-end">
      {editing && status === 'scheduled' && (
        <button type="button" className="btn-danger px-4 py-2" disabled={busy} onClick={() => onCancelQueued(post)}>
          {busy ? <Loader2 size={15} className="animate-spin" /> : null} {t('cal.cancelq')}
        </button>
      )}
      {editing && status !== 'scheduled' && (
        <button type="button" className="btn-danger px-4 py-2" disabled={busy} onClick={() => onDelete(post)}>{t('cal.delete')}</button>
      )}
      {editing && EDITABLE.includes(status) && (
        <button type="button" className="btn-secondary px-4 py-2" disabled={saving || !valid} onClick={submit}>{t('cal.save.changes')}</button>
      )}
      {editing && EDITABLE.includes(status) && (
        <button type="button" className="btn-primary px-5 py-2" disabled={busy || !canSend} title={canSend ? undefined : t('cal.send.nokey')} onClick={() => onSend(post)}>
          {busy ? <><Loader2 size={15} className="animate-spin" /> {t('cal.sending')}</> : t('cal.send')}
        </button>
      )}
      {!editing && (
        <button type="button" className="btn-primary px-5 py-2" disabled={saving || !valid} onClick={submit}>
          {saving ? <><Loader2 size={15} className="animate-spin" /> {t('cal.form.saving')}</> : t('cal.form.save')}
        </button>
      )}
    </div>
  );

  return (
    <Modal isOpen onClose={saving || busy ? undefined : onClose} size="md" title={editing ? t('cal.form.edit') : t('cal.form.title')} footer={footer}>
      {editing && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <span className={STATUS_TONE[status]}>{t(`cal.status.${status}`)}</span>
          {status === 'published' && <span className="text-xs text-muted">{t('cal.status.published.tip')}</span>}
          {status === 'failed' && post.error && <span className="text-xs text-danger break-words">{post.error}</span>}
        </div>
      )}
      <div className="space-y-4">
        {!editing && (
          <>
            <label className="block">
              <span className="eyebrow">{t('cal.project')}</span>
              <select className="input-field mt-1.5" value={f.jobId} onChange={(e) => pickProject(e.target.value)}>
                <option value="">{t('cal.project.none')}</option>
                {projects.map((p) => <option key={p.job_id} value={p.job_id}>{p.title}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="eyebrow">{t('cal.form.clip')}</span>
              <select className="input-field mt-1.5" value={f.clip} disabled={!f.jobId || !clips} onChange={(e) => pickClip(e.target.value)}>
                <option value="">{f.jobId && !clips ? t('cal.clips.loading') : t('cal.form.pick')}</option>
                {(clips || []).map((c, i) => (
                  <option key={i} value={i}>{t('cal.clip.n', { n: i + 1 })} · {clipView(c, t, i + 1).title}</option>
                ))}
              </select>
            </label>
          </>
        )}
        {editing && (
          <p className="text-sm text-ink2 truncate">{t('cal.clip.n', { n: post.clip_index + 1 })}</p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="eyebrow">{t('cal.form.date')}</span>
            <input type="date" className="input-field mt-1.5" value={f.date} disabled={locked}
              onChange={(e) => setF({ ...f, date: e.target.value })} />
          </label>
          <label className="block">
            <span className="eyebrow">{t('cal.form.time')}</span>
            <input type="time" className="input-field mt-1.5" value={f.time} disabled={locked}
              onChange={(e) => setF({ ...f, time: e.target.value })} />
          </label>
        </div>
        <p className="text-xs text-muted -mt-2">{t('cal.tz', { tz: editing ? post.timezone : browserTz() })}</p>
        <div>
          <span className="eyebrow block mb-1.5">{t('cal.form.platforms')}</span>
          <SegmentedControl multi options={PLATFORMS.map((p) => ({ ...p, disabled: locked }))} value={f.platforms}
            onChange={(arr) => setF({ ...f, platforms: arr })} />
        </div>
        {f.platforms.includes('tiktok') && !locked && <TikTokDraftNotice />}
        <label className="block">
          <span className="eyebrow">{t('cal.form.caption')}</span>
          <input className="input-field mt-1.5" maxLength={200} value={f.title} disabled={locked}
            onChange={(e) => setF({ ...f, title: e.target.value })} />
        </label>
        <label className="block">
          <span className="eyebrow">{t('cal.form.desc')}</span>
          <textarea className="input-field mt-1.5 min-h-[88px]" maxLength={2200} value={f.description} disabled={locked}
            onChange={(e) => setF({ ...f, description: e.target.value })} />
        </label>
        {locked && status === 'scheduled' && <p className="text-xs text-muted">{t('cal.locked')}</p>}
        {editing && !canSend && EDITABLE.includes(status) && <p className="text-xs text-warn">{t('cal.send.nokey')}</p>}
        {err && <p role="alert" className="text-sm text-danger bg-danger/10 rounded-input px-3 py-2">{err}</p>}
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------------------------
function KeyCard({ connected, onConnected }) {
  const { t } = useLang();
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ bad: false, text: '' });
  if (connected) {
    return <p className="text-xs text-ok flex items-center gap-1.5"><Check size={13} /> {t('cal.key.ok')}</p>;
  }
  const save = async () => {
    const key = value.trim();
    if (!key) return;
    setBusy(true); setMsg({ bad: false, text: '' });
    try {
      const res = await apiFetch('/api/social/user', { headers: { 'X-Upload-Post-Key': key } });
      if (!res.ok) throw new Error('bad key');
      const data = await res.json();
      const first = data.profiles?.[0]?.username;
      if (!first) { setMsg({ bad: true, text: t('cal.key.noprofile') }); return; }
      setUploadPostKey(key);
      if (!getUploadUserId()) setUploadUserId(first);
      setValue('');
      onConnected();
    } catch (_) { setMsg({ bad: true, text: t('cal.key.fail') }); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-input border border-rule bg-paper2 p-3 space-y-2">
      <p className="text-sm font-medium text-ink flex items-center gap-1.5"><KeyRound size={14} className="text-brass" /> {t('cal.key.title')}</p>
      <p className="text-xs text-muted">{t('cal.key.text')}</p>
      <input className="input-field" type="password" autoComplete="off" aria-label={t('cal.key.input')} placeholder={t('cal.key.input')}
        value={value} onChange={(e) => setValue(e.target.value)} />
      <button type="button" className="btn-secondary px-4 py-2" disabled={busy || !value.trim()} onClick={save}>
        {busy && <Loader2 size={14} className="animate-spin" />} {t('cal.key.save')}
      </button>
      {msg.text && <p role="alert" className={`text-xs ${msg.bad ? 'text-danger' : 'text-ok'}`}>{msg.text}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
export default function CalendarPage() {
  const { t, lang } = useLang();
  const { isManaged } = useAuth();
  const errText = useErr(t);
  const [view, setView] = useState('month');
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [posts, setPosts] = useState([]);
  const [external, setExternal] = useState([]);
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState([]);
  const [projectsReady, setProjectsReady] = useState(false);
  const [jobId, setJobId] = useState('');
  const [clipsByJob, setClipsByJob] = useState({});
  const [modal, setModal] = useState(null);       // { post } | { draft }
  const [daySheet, setDaySheet] = useState(null); // a Date
  const [weekOpen, setWeekOpen] = useState(false);
  const [notice, setNotice] = useState({ bad: false, text: '' });
  const [busy, setBusy] = useState(false);
  const [keyTick, setKeyTick] = useState(0);
  const fetching = useRef({});

  const upKey = useMemo(() => getUploadPostKey(), [keyTick]);   // eslint-disable-line react-hooks/exhaustive-deps
  const upUser = useMemo(() => getUploadUserId(), [keyTick]);   // eslint-disable-line react-hooks/exhaustive-deps
  const canSend = !!(upKey && upUser);

  const days = useMemo(() => {
    if (view === 'week') {
      const s = mondayOf(anchor);
      return Array.from({ length: 7 }, (_, i) => addDays(s, i));
    }
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const s = mondayOf(first);
    return Array.from({ length: 42 }, (_, i) => addDays(s, i));
  }, [view, anchor]);
  // Plain numbers: a Date made on every render would be a new dependency each time and loop `load`.
  const rangeStart = days[0].getTime();
  const rangeEnd = addDays(days[days.length - 1], 1).getTime();
  const todayKey = ymd(new Date());

  const flash = (text, bad = false) => { setNotice({ bad, text }); };

  // Posts in range, plus (when connected) what Upload-Post still has pending.
  const load = useCallback(async () => {
    setLoading(true);
    let list = [];
    try {
      list = (await calendarApi.list(rangeStart / 1000, rangeEnd / 1000)).items;
    } catch (_) { list = []; }
    let pending = null;
    if (upKey && upUser) {
      try {
        const res = await apiFetch(`/api/social/scheduled?user=${encodeURIComponent(upUser)}`, { headers: { 'X-Upload-Post-Key': upKey } });
        if (res.ok) pending = (await res.json()).scheduled_posts || [];
      } catch (_) { pending = null; }
    }
    if (pending) {
      const ids = new Set(pending.map((p) => String(p.job_id)));
      // Sent posts that left the queue after their time were published (or dropped by the network).
      const gone = list.filter((p) => p.status === 'scheduled' && p.vendor_job_id && !ids.has(String(p.vendor_job_id))
        && p.scheduled_for * 1000 < Date.now() - 5 * 60000);
      for (const p of gone) {
        try { const saved = await calendarApi.setStatus(p.id, 'published'); list = list.map((x) => (x.id === p.id ? saved : x)); } catch (_) { /* next load retries */ }
      }
      const known = new Set(list.map((p) => String(p.vendor_job_id)));
      setExternal(pending.filter((p) => !known.has(String(p.job_id)) && p.scheduled_date)
        .map((p) => ({ id: `x${p.job_id}`, when: new Date(p.scheduled_date), title: p.title || p.post_title || '', platforms: p.platforms || p.platform || [] }))
        .filter((p) => !Number.isNaN(p.when.getTime()) && p.when.getTime() >= rangeStart && p.when.getTime() < rangeEnd));
    } else {
      setExternal([]);
    }
    setPosts(list);
    setLoading(false);
  }, [rangeStart, rangeEnd, upKey, upUser]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    let live = true;
    projectsApi.list({ status: 'completed', limit: 100 })
      .then((r) => { if (live) { setProjects(r.items || []); setProjectsReady(true); } })
      .catch(() => { if (live) setProjectsReady(true); });
    return () => { live = false; };
  }, []);

  const ensureClips = useCallback(async (id) => {
    if (!id || fetching.current[id]) return;
    fetching.current[id] = true;
    try {
      const res = await apiFetch(`/api/status/${encodeURIComponent(id)}`);
      const data = res.ok ? await res.json() : null;
      setClipsByJob((m) => ({ ...m, [id]: data?.result?.clips || [] }));
    } catch (_) {
      setClipsByJob((m) => ({ ...m, [id]: [] }));
    }
  }, []);

  useEffect(() => { if (jobId) ensureClips(jobId); }, [jobId, ensureClips]);

  const byDay = useMemo(() => {
    const map = {};
    posts.forEach((p) => { (map[ymd(new Date(p.scheduled_for * 1000))] ||= []).push({ kind: 'post', ...p }); });
    external.forEach((p) => { (map[ymd(p.when)] ||= []).push({ kind: 'ext', ...p }); });
    return map;
  }, [posts, external]);

  const move = (dir) => setAnchor((a) => (view === 'week' ? addDays(a, 7 * dir) : new Date(a.getFullYear(), a.getMonth() + dir, 1)));
  const heading = view === 'week'
    ? `${days[0].toLocaleDateString(lang, { day: 'numeric', month: 'short' })} – ${days[6].toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' })}`
    : anchor.toLocaleDateString(lang, { month: 'long', year: 'numeric' });

  const openCreate = (date, extra = {}) => setModal({ draft: { date: ymd(date), jobId, ...extra } });

  const onDrop = async (e, date) => {
    e.preventDefault();
    const clipRaw = e.dataTransfer.getData('application/x-vs-clip');
    const postRaw = e.dataTransfer.getData('application/x-vs-post');
    if (clipRaw) {
      const c = JSON.parse(clipRaw);
      const v = clipView(clipsByJob[c.jobId]?.[c.clip], t, c.clip + 1);
      openCreate(date, { jobId: c.jobId, clip: c.clip, title: v.title, description: v.description });
    } else if (postRaw) {
      const p = posts.find((x) => x.id === Number(postRaw));
      if (!p) return;
      if (!EDITABLE.includes(p.status)) { flash(t('cal.drop.locked'), true); return; }
      const old = new Date(p.scheduled_for * 1000);
      const target = new Date(date.getFullYear(), date.getMonth(), date.getDate(), old.getHours(), old.getMinutes());
      try {
        const saved = await calendarApi.update(p.id, { scheduled_for: target.getTime() / 1000 });
        setPosts((l) => l.map((x) => (x.id === saved.id ? saved : x)));
        flash('');
      } catch (err) { flash(errText(err), true); }
    }
  };

  const onSaved = (saved) => {
    setModal(null);
    setPosts((l) => {
      const without = l.filter((x) => x.id !== saved.id);
      const when = saved.scheduled_for * 1000;
      return when >= rangeStart && when < rangeEnd ? [...without, saved] : without;
    });
    setDaySheet(null);
  };

  const send = async (post) => {
    setBusy(true); flash('');
    try {
      const body = { job_id: post.job_id, clip_index: post.clip_index, api_key: upKey, user_id: upUser, platforms: post.platforms,
        title: post.title, description: post.description, scheduled_date: wallClock(post.scheduled_for, post.timezone), timezone: post.timezone };
      const res = await apiFetch('/api/social/post', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!res.ok) {
        const text = (await res.text()).slice(0, 280);
        const saved = await calendarApi.setStatus(post.id, 'failed', { error: text });
        setPosts((l) => l.map((x) => (x.id === saved.id ? saved : x)));
        setModal({ post: saved });
        return;
      }
      const data = await res.json().catch(() => ({}));
      const saved = await calendarApi.setStatus(post.id, 'scheduled', { vendorJobId: String(data.job_id || data.request_id || data.id || '') });
      setPosts((l) => l.map((x) => (x.id === saved.id ? saved : x)));
      setModal(null);
      flash(t('cal.sent'));
    } catch (e) { flash(errText(e), true); } finally { setBusy(false); }
  };

  const cancelQueued = async (post) => {
    setBusy(true); flash('');
    try {
      if (post.vendor_job_id) {
        const res = await apiFetch(`/api/social/scheduled/${encodeURIComponent(post.vendor_job_id)}?user=${encodeURIComponent(upUser)}`,
          { method: 'DELETE', headers: { 'X-Upload-Post-Key': upKey } });
        if (!res.ok) throw new Error('cancel');
      }
      const saved = await calendarApi.setStatus(post.id, 'cancelled');
      setPosts((l) => l.map((x) => (x.id === saved.id ? saved : x)));
      setModal(null);
      flash(t('cal.cancelq.done'));
    } catch (e) { flash(e?.code ? errText(e) : t('cal.err.generic'), true); } finally { setBusy(false); }
  };

  const remove = async (post) => {
    setBusy(true);
    try {
      await calendarApi.remove(post.id);
      setPosts((l) => l.filter((x) => x.id !== post.id));
      setModal(null);
    } catch (e) { flash(errText(e), true); } finally { setBusy(false); }
  };

  const weekClips = clipsByJob[jobId] || [];
  const weekDays = ['0', '1', '2', '3', '4', '5', '6'];
  const dayChips = (list, max) => {
    const shown = list.slice(0, max);
    return { shown, more: list.length - shown.length };
  };

  const chip = (p) => (
    p.kind === 'ext' ? (
      <div key={p.id} title={t('cal.external')} className="flex items-center gap-1.5 rounded-md border border-dashed border-rule-2 px-1.5 py-1 text-[0.6875rem] text-muted truncate">
        <ExternalLink size={10} className="shrink-0" /> <span className="truncate">{hm(p.when)} {p.title}</span>
      </div>
    ) : (
      <button key={p.id} type="button" draggable={EDITABLE.includes(p.status)}
        onDragStart={(e) => e.dataTransfer.setData('application/x-vs-post', String(p.id))}
        onClick={(e) => { e.stopPropagation(); setModal({ post: p }); }}
        className="w-full flex items-center gap-1.5 rounded-md bg-paper3 hover:bg-accent-soft border border-rule px-1.5 py-1 text-left text-[0.6875rem] text-ink2 truncate transition-colors">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${DOT_TONE[p.status]}`} aria-hidden="true" />
        <span className="tabular-nums shrink-0">{hm(new Date(p.scheduled_for * 1000))}</span>
        <span className="truncate">{p.title || t('cal.clip.n', { n: p.clip_index + 1 })}</span>
        <span className="sr-only">{t(`cal.status.${p.status}`)}</span>
      </button>
    )
  );

  return (
    <StudioShell active="calendar" wide>
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h1 className="font-display text-3xl text-ink">{t('cal.title')}</h1>
          <p className="text-sm text-muted mt-1">{t('cal.sub')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-secondary !py-2 !px-4" onClick={() => setWeekOpen(true)} disabled={!jobId || !weekClips.length}
            title={!jobId ? t('cal.project.none') : undefined}>
            <CalendarDays size={15} /> {t('cal.week.plan')}
          </button>
          <button type="button" className="btn-primary !py-2 !px-5" onClick={() => openCreate(startOfDay(new Date()))}>
            <Plus size={16} /> {t('cal.add')}
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_300px] gap-6 items-start">
        <section className="card p-3 sm:p-5 min-w-0" aria-label={t('cal.title')}>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-1.5">
              <button type="button" className="btn-quiet !p-2" aria-label={t('cal.prev')} onClick={() => move(-1)}><ChevronLeft size={16} /></button>
              <button type="button" className="btn-quiet !px-3 !py-2 whitespace-nowrap" onClick={() => setAnchor(startOfDay(new Date()))}>{t('cal.today')}</button>
              <button type="button" className="btn-quiet !p-2" aria-label={t('cal.next')} onClick={() => move(1)}><ChevronRight size={16} /></button>
              <h2 className="font-display text-lg text-ink ml-2 capitalize" aria-live="polite">{heading}</h2>
              {loading && <Loader2 size={15} className="animate-spin text-muted ml-1" aria-label={t('cal.loading')} />}
            </div>
            <div className="w-44">
              <SegmentedControl size="sm" columns={2} value={view} onChange={setView}
                options={[{ value: 'month', label: t('cal.view.month') }, { value: 'week', label: t('cal.view.week') }]} />
            </div>
          </div>
          {notice.text && (
            <p role={notice.bad ? 'alert' : 'status'} className={`text-sm rounded-input px-3 py-2 mb-3 ${notice.bad ? 'text-danger bg-danger/10' : 'text-ok bg-ok/10'}`}>{notice.text}</p>
          )}
          <div className="grid grid-cols-7 text-center text-[0.6875rem] uppercase tracking-wide text-muted mb-1" aria-hidden="true">
            {weekDays.map((i) => <div key={i} className="py-1">{new Date(2024, 0, 1 + Number(i)).toLocaleDateString(lang, { weekday: 'short' })}</div>)}
          </div>
          <div className="grid grid-cols-7 gap-px bg-rule border border-rule rounded-input overflow-hidden">
            {days.map((d) => {
              const key = ymd(d);
              const list = byDay[key] || [];
              const { shown, more } = dayChips(list, view === 'week' ? 8 : 3);
              const muted = view === 'month' && d.getMonth() !== anchor.getMonth();
              const today = key === todayKey;
              return (
                <div key={key}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => onDrop(e, d)}
                  onClick={() => (window.innerWidth < 640 ? setDaySheet(d) : openCreate(d))}
                  className={`group relative bg-paper ${view === 'week' ? 'min-h-[220px]' : 'min-h-[68px] sm:min-h-[104px]'} p-1 sm:p-1.5 cursor-pointer hover:bg-paper2 transition-colors ${muted ? 'opacity-50' : ''}`}>
                  <div className="flex items-center justify-between">
                    <span className={`text-xs tabular-nums w-6 h-6 inline-flex items-center justify-center rounded-full ${today ? 'bg-brand text-brassink font-semibold' : 'text-ink2'}`}>{d.getDate()}</span>
                    <button type="button" aria-label={`${t('cal.add')} ${d.toLocaleDateString(lang)}`}
                      onClick={(e) => { e.stopPropagation(); openCreate(d); }}
                      className="hidden sm:inline-flex opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded-full text-muted hover:text-ink"><Plus size={13} /></button>
                  </div>
                  {/* Phone: dots only (the day sheet lists them); from sm: the posts themselves. */}
                  <div className="sm:hidden flex flex-wrap gap-1 mt-1 px-0.5">
                    {list.slice(0, 6).map((p) => <span key={p.id} className={`w-1.5 h-1.5 rounded-full ${p.kind === 'ext' ? 'bg-muted' : DOT_TONE[p.status]}`} />)}
                  </div>
                  <div className="hidden sm:block mt-1 space-y-1">
                    {shown.map(chip)}
                    {more > 0 && (
                      <button type="button" onClick={(e) => { e.stopPropagation(); setDaySheet(d); }} className="text-[0.6875rem] text-muted hover:text-ink px-1">{t('cal.more', { n: more })}</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {!loading && !posts.length && !external.length && (
            <p className="text-sm text-muted text-center mt-4">{t('cal.empty')}</p>
          )}
        </section>

        <aside className="space-y-4 min-w-0">
          <section className="card p-4 space-y-3">
            <h2 className="font-display text-lg text-ink">{t('cal.clips')}</h2>
            {!projectsReady ? (
              <div className="skeleton h-10" />
            ) : !projects.length ? (
              <EmptyState compact icon={<Film size={22} />} text={t('cal.project.empty')}
                action={<a href="#/projects" className="btn-secondary !py-2 !px-4">{t('shell.projects')}</a>} />
            ) : (
              <>
                <label className="block">
                  <span className="eyebrow">{t('cal.project')}</span>
                  <select className="input-field mt-1.5" value={jobId} onChange={(e) => setJobId(e.target.value)}>
                    <option value="">{t('cal.project.none')}</option>
                    {projects.map((p) => <option key={p.job_id} value={p.job_id}>{p.title}</option>)}
                  </select>
                </label>
                <p className="text-xs text-muted">{t('cal.clips.hint')}</p>
                {jobId && !clipsByJob[jobId] && <div className="skeleton h-14" />}
                {jobId && clipsByJob[jobId] && !weekClips.length && <p className="text-sm text-muted">{t('cal.clips.empty')}</p>}
                <ul className="space-y-2 max-h-[22rem] overflow-y-auto custom-scrollbar pr-1">
                  {weekClips.map((c, i) => {
                    const v = clipView(c, t, i + 1);
                    return (
                      <li key={i}>
                        <div draggable
                          onDragStart={(e) => e.dataTransfer.setData('application/x-vs-clip', JSON.stringify({ jobId, clip: i }))}
                          className="flex items-center gap-2 rounded-input border border-rule bg-paper2 p-2 cursor-grab active:cursor-grabbing">
                          <GripVertical size={14} className="text-muted shrink-0" aria-hidden="true" />
                          <span className="flex-1 min-w-0">
                            <span className="block text-sm text-ink truncate">{v.title}</span>
                            <span className="readout !normal-case">{t('cal.clip.n', { n: i + 1 })}</span>
                          </span>
                          <button type="button" className="btn-quiet !p-1.5" aria-label={`${t('cal.add')}: ${v.title}`}
                            onClick={() => openCreate(startOfDay(new Date()), { jobId, clip: i, title: v.title, description: v.description })}><Plus size={14} /></button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}
          </section>
          <section className="card p-4">
            <KeyCard connected={canSend} onConnected={() => setKeyTick((n) => n + 1)} />
          </section>
        </aside>
      </div>

      {modal && (
        <PostModal key={modal.post ? `p${modal.post.id}:${modal.post.status}` : 'new'} state={modal}
          onClose={() => setModal(null)} projects={projects} clipsByJob={clipsByJob} ensureClips={ensureClips}
          onSaved={onSaved} onSend={send} onCancelQueued={cancelQueued} onDelete={remove} canSend={canSend} busy={busy} />
      )}

      <Modal isOpen={!!daySheet} onClose={() => setDaySheet(null)} size="md"
        title={daySheet ? daySheet.toLocaleDateString(lang, { weekday: 'long', day: 'numeric', month: 'long' }) : ''}
        footer={daySheet && (
          <button type="button" className="btn-primary w-full" onClick={() => { const d = daySheet; setDaySheet(null); openCreate(d); }}>
            <Plus size={16} /> {t('cal.add')}
          </button>
        )}>
        <div className="space-y-2">
          {daySheet && (byDay[ymd(daySheet)] || []).length === 0 && <p className="text-sm text-muted">{t('cal.day.none')}</p>}
          {daySheet && (byDay[ymd(daySheet)] || []).map((p) => (p.kind === 'ext' ? (
            <div key={p.id} className="rounded-input border border-dashed border-rule-2 p-3 text-sm text-muted">{hm(p.when)} · {p.title || t('cal.external')}</div>
          ) : (
            <button key={p.id} type="button" onClick={() => { setDaySheet(null); setModal({ post: p }); }}
              className="w-full text-left rounded-input border border-rule bg-paper2 p-3 flex items-center gap-3">
              <span className="tabular-nums text-sm text-ink2">{hm(new Date(p.scheduled_for * 1000))}</span>
              <span className="flex-1 min-w-0 text-sm text-ink truncate">{p.title || t('cal.clip.n', { n: p.clip_index + 1 })}</span>
              <span className={STATUS_TONE[p.status]}>{t(`cal.status.${p.status}`)}</span>
            </button>
          )))}
        </div>
      </Modal>

      <ScheduleWeekModal isOpen={weekOpen} onClose={() => { setWeekOpen(false); load(); }} clips={weekClips} jobId={jobId}
        uploadPostKey={upKey} uploadUserId={upUser} isManaged={!!isManaged} />
    </StudioShell>
  );
}
