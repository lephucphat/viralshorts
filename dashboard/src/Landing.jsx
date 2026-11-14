import React, { useEffect, useId, useRef, useState } from 'react';
import {
  ArrowRight, ChevronDown, Scissors, TrendingUp, Type, Wand2, Languages, Share2,
  Globe, Sun, Moon, Monitor, Upload, Sparkles, Film, Check, Link2,
} from 'lucide-react';
import { useLang } from './contexts/LangContext';
import { useTheme } from './contexts/ThemeContext';
import { useAuth } from './contexts/AuthContext';
import { billingApi } from './lib/studio';
import { isVideoUrl, setPendingSource } from './lib/pendingSource';
import { openConsentManager } from './lib/consent';
import { SUPPORT_EMAIL } from '../seo/site.js';

// ViralShorts landing page. Keep seo/crawler-content.js in step with the claims made here:
// that file is what clients that do not run JavaScript read.
//
// Rules for this page: no user counts, no customer logos, no testimonials, no ratings.
// There is nothing real to put there yet, so nothing is shown. The demo area is either a
// real video (VITE_LANDING_DEMO_VIDEO, set at build time) or an honest, labelled CSS mock-up.
const DEMO_VIDEO = import.meta.env.VITE_LANDING_DEMO_VIDEO || '';
const DEMO_POSTER = import.meta.env.VITE_LANDING_DEMO_POSTER || '';

// Decorative gradients only; they are illustration, not UI chrome, so they are
// the one place a raw colour is fine.
const ORBS = {
  clips: 'radial-gradient(circle at 30% 25%, #ffe2c7 0%, #ff9a5a 38%, #c2410c 78%)',
  score: 'radial-gradient(circle at 30% 25%, #e9d5ff 0%, #a78bfa 40%, #4c1d95 80%)',
  captions: 'radial-gradient(circle at 30% 25%, #d1fae5 0%, #34d399 40%, #065f46 80%)',
  hook: 'radial-gradient(circle at 30% 25%, #fde68a 0%, #f59e0b 40%, #92400e 80%)',
  dub: 'radial-gradient(circle at 30% 25%, #bfdbfe 0%, #60a5fa 40%, #1e3a8a 80%)',
  publish: 'radial-gradient(circle at 30% 25%, #fbcfe8 0%, #f472b6 40%, #831843 80%)',
};

const TABS = [
  { id: 'clips', icon: Scissors },
  { id: 'score', icon: TrendingUp },
  { id: 'captions', icon: Type },
  { id: 'hook', icon: Wand2 },
  { id: 'dub', icon: Languages },
  { id: 'publish', icon: Share2 },
];

const FEATURES = [
  { icon: Scissors, k: 'f1' },
  { icon: TrendingUp, k: 'f2' },
  { icon: Globe, k: 'f3' },
  { icon: Film, k: 'f4' },
  { icon: Languages, k: 'f5' },
  { icon: Share2, k: 'f6' },
];

const STEPS = ['s1', 's2', 's3'];
const STEP_ICONS = [Link2, Wand2, Share2];
const PLATFORMS = ['TikTok', 'Instagram Reels', 'YouTube Shorts'];
// q1-q5 live in i18n.js (land.*); q6-q8 in i18n.landing.js (lp.*).
const FAQS = [
  ['q1', 'land'], ['q2', 'land'], ['q3', 'land'], ['q4', 'land'], ['q5', 'land'],
  ['q6', 'lp'], ['q7', 'lp'], ['q8', 'lp'],
];

const money = (amount, vnd, lang) => (vnd
  ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(amount)
  : new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency: 'USD' }).format(amount / 100));

const hasRealEmail = !SUPPORT_EMAIL.startsWith('[');

function Eyebrow({ children }) {
  return <p className="eyebrow !text-brass">{children}</p>;
}

function PhoneMock({ tab, t }) {
  return (
    <div className="relative mx-auto w-[210px] sm:w-[240px] aspect-[9/16] rounded-[30px] overflow-hidden border border-rule shadow-pop bg-black">
      <div className="absolute inset-0" style={{ background: ORBS[tab] }} />
      <div className="absolute inset-0 bg-gradient-to-b from-black/10 via-transparent to-black/55" />
      {/* the overlay changes with the tab so the picture matches the claim */}
      {tab === 'hook' && (
        <div className="absolute top-6 inset-x-4 rounded-xl bg-white/95 text-black text-[0.8125rem] font-semibold px-3 py-2 text-center">
          {t('land.mock.hook')}
        </div>
      )}
      {tab === 'score' && (
        <div className="absolute top-4 left-4 rounded-full bg-black/70 text-white text-[0.6875rem] px-2.5 py-1 flex items-center gap-1.5">
          <TrendingUp size={11} /> viral
        </div>
      )}
      {tab === 'clips' && (
        <div className="absolute inset-5 border-2 border-white/80 rounded-2xl">
          <span className="absolute -top-2.5 left-3 bg-white text-black text-[0.625rem] px-2 py-0.5 rounded-full">9:16</span>
        </div>
      )}
      {tab === 'dub' && (
        <div className="absolute top-4 right-4 flex gap-1.5">
          {['EN', 'VI', 'JA'].map((l) => (
            <span key={l} className="rounded-full bg-black/60 text-white text-[0.625rem] px-2 py-0.5">{l}</span>
          ))}
        </div>
      )}
      {tab === 'publish' && (
        <div className="absolute top-4 inset-x-4 flex justify-center gap-2">
          {['TikTok', 'Reels', 'Shorts'].map((p) => (
            <span key={p} className="rounded-full bg-white/90 text-black text-[0.625rem] px-2 py-0.5">{p}</span>
          ))}
        </div>
      )}
      <div className="absolute bottom-8 inset-x-4 text-center text-white text-[0.9375rem] font-bold leading-tight drop-shadow">
        {tab === 'captions' ? <><span className="bg-yellow-300 text-black px-1 rounded">{t('land.mock.cap1')}</span> {t('land.mock.cap2')}</> : t('land.mock.cap')}
      </div>
    </div>
  );
}

// The demo area. A real video when one is configured; otherwise the CSS mock-up, labelled as such.
function DemoSlot({ tab, t }) {
  if (DEMO_VIDEO) {
    return (
      <div className="mx-auto w-[210px] sm:w-[240px] aspect-[9/16] rounded-[30px] overflow-hidden border border-rule shadow-pop bg-black">
        <video src={DEMO_VIDEO} poster={DEMO_POSTER || undefined} controls playsInline preload="none"
          aria-label={t('lp.demo.video')} className="w-full h-full object-cover" />
      </div>
    );
  }
  return (
    <figure className="m-0">
      <PhoneMock tab={tab} t={t} />
      <figcaption className="mt-3 text-center text-xs text-muted">
        <span className="chip !py-0.5 !px-2.5 !text-xs">{t('lp.demo.label')}</span>
        <span className="block mt-1.5 max-w-[240px] mx-auto">{t('lp.demo.note')}</span>
      </figcaption>
    </figure>
  );
}

// The first thing on the page: paste a link or choose a file. Nothing is sent anywhere here;
// the link waits in sessionStorage until the visitor has an account (see lib/pendingSource).
function StartBox({ t, onLaunchApp, big = false }) {
  const { isSignedIn } = useAuth();
  const [link, setLink] = useState('');
  const [error, setError] = useState('');
  const [fileNote, setFileNote] = useState(false);
  const fileRef = useRef(null);
  const inputId = useId();

  const submit = (e) => {
    e.preventDefault();
    const value = link.trim();
    if (!isVideoUrl(value)) { setError(t('lp.start.invalid')); return; }
    setError('');
    setPendingSource(value);
    onLaunchApp();
  };

  const picked = (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setFileNote(true);
    onLaunchApp();
  };

  return (
    <div className={`w-full max-w-2xl mx-auto ${big ? '' : ''}`}>
      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2" noValidate>
        <div className="relative flex-1">
          <label htmlFor={inputId} className="sr-only">{t('lp.start.label')}</label>
          <Link2 size={17} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
          <input id={inputId} type="url" inputMode="url" autoComplete="off" value={link}
            onChange={(e) => { setLink(e.target.value); if (error) setError(''); }}
            placeholder={t('lp.start.placeholder')} aria-invalid={!!error} aria-describedby={error ? `${inputId}-err` : undefined}
            className="input-field pl-11 !py-3.5 !rounded-full shadow-card w-full" />
        </div>
        <button type="submit" className="btn-primary !px-7 !py-3.5 whitespace-nowrap">
          {t('lp.start.go')} <ArrowRight size={16} />
        </button>
      </form>
      {error && <p id={`${inputId}-err`} role="alert" className="mt-2 text-sm text-danger text-left sm:text-center">{error}</p>}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5 text-sm">
        <button type="button" onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-2 text-ink2 hover:text-ink transition-colors">
          <Upload size={15} /> {t('lp.start.upload')}
        </button>
        <span className="text-muted">{isSignedIn ? t('lp.start.signedin') : t('lp.start.note')}</span>
      </div>
      {fileNote && !isSignedIn && <p role="status" className="mt-2 text-xs text-muted text-center">{t('lp.start.file')}</p>}
      <input ref={fileRef} type="file" accept="video/*,.mkv,.mov,.mp4,.webm" className="hidden" onChange={picked} tabIndex={-1} aria-hidden="true" />
    </div>
  );
}

function PricingTeaser({ t, lang }) {
  const [catalog, setCatalog] = useState(null);   // null = loading, false = failed
  useEffect(() => {
    let live = true;
    billingApi.plans()
      .then((c) => live && setCatalog(c))
      .catch(() => live && setCatalog(false));
    return () => { live = false; };
  }, []);

  const vnd = lang === 'vi';
  const plans = catalog ? catalog.plans || [] : [];
  return (
    <section id="plans" className="border-t border-rule bg-paper2/40">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
        <Eyebrow>{t('lp.price.eyebrow')}</Eyebrow>
        <h2 className="font-display text-3xl sm:text-4xl max-w-xl mt-2">{t('land.price.title')}</h2>
        <p className="mt-4 text-ink2 max-w-2xl leading-relaxed">{t('land.price.sub')}</p>
        {plans.length > 0 && (
          <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {plans.map((p) => {
              const amount = vnd ? p.price_vnd : p.price_usd_cents;
              const featured = p.id === 'pro';
              return (
                <div key={p.id} className={`card p-6 flex flex-col ${featured ? 'ring-1 ring-brass shadow-pop' : ''}`}>
                  <h3 className="font-display text-xl text-ink">{amount ? p.name : t('land.price.free')}</h3>
                  <p className="mt-3 text-3xl font-display text-ink tabular-nums">
                    {money(amount || 0, vnd, lang)}
                    <span className="text-sm text-muted font-sans"> {t('billing.per_month')}</span>
                  </p>
                  <ul className="mt-4 space-y-2 text-sm text-ink2">
                    <li className="flex gap-2"><Check size={15} className="text-ok mt-0.5 shrink-0" />{t('lp.price.credits', { n: p.credits.toLocaleString(vnd ? 'vi-VN' : 'en-US') })}</li>
                    <li className="flex gap-2"><Check size={15} className="text-ok mt-0.5 shrink-0" />{t('billing.retention', { n: p.retention_days })}</li>
                  </ul>
                </div>
              );
            })}
          </div>
        )}
        {catalog === false && <p className="mt-8 text-sm text-muted">{t('land.price.error')}</p>}
        {catalog && catalog.prices_placeholder && <p className="mt-6 text-sm text-warn">{t('lp.price.placeholder')}</p>}
        <p className="mt-4 text-sm text-muted">{t('land.price.topup')} {t(vnd ? 'land.price.vnd' : 'land.price.usd')}</p>
        <a href="#/pricing" className="btn-secondary mt-6 no-underline">{t('land.price.all')} <ArrowRight size={16} /></a>
      </div>
    </section>
  );
}

function Faq({ t }) {
  const [open, setOpen] = useState(null);
  const base = useId();
  return (
    <div className="mt-8 card divide-y divide-rule overflow-hidden">
      {FAQS.map(([q, ns]) => {
        const isOpen = open === q;
        const buttonId = `${base}-${q}-b`;
        const panelId = `${base}-${q}-p`;
        return (
          <div key={q}>
            <h3>
              <button type="button" id={buttonId} onClick={() => setOpen(isOpen ? null : q)} aria-expanded={isOpen} aria-controls={panelId}
                className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left text-ink font-medium hover:bg-paper3/50 transition-colors">
                {t(`${ns}.${q}.q`)}
                <ChevronDown size={18} className={`shrink-0 text-muted transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
              </button>
            </h3>
            <div id={panelId} role="region" aria-labelledby={buttonId} hidden={!isOpen}>
              <p className="px-5 pb-5 text-sm leading-relaxed text-ink2">{t(`${ns}.${q}.a`)}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ThemeButton({ t }) {
  const { mode, setMode } = useTheme();
  const next = { light: 'dark', dark: 'system', system: 'light' };
  const Icon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor;
  return (
    <button type="button" onClick={() => setMode(next[mode] || 'light')} aria-label={t('theme.tip')}
      className="p-2 rounded-full text-muted hover:text-ink hover:bg-paper3 transition-colors">
      <Icon size={16} />
    </button>
  );
}

function FooterColumn({ title, children }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <ul className="mt-3 space-y-2 text-sm text-muted list-none p-0 m-0">{children}</ul>
    </div>
  );
}

export default function Landing({ onLaunchApp }) {
  const { t, lang, setLang } = useLang();
  const { isSignedIn } = useAuth();
  const [tab, setTab] = useState('clips');
  const linkCls = 'text-ink2 hover:text-ink transition-colors';
  const footLink = 'hover:text-ink transition-colors';

  return (
    <div className="min-h-screen bg-paper text-ink2">
      {/* top bar */}
      <header className="sticky top-0 z-30 bg-paper/85 backdrop-blur border-b border-rule">
        <div className="max-w-6xl mx-auto h-16 px-4 sm:px-6 flex items-center gap-6">
          <a href="#landing" className="flex items-center gap-2.5 shrink-0">
            <img src="/logo-viralshorts.png" alt="" className="w-7 h-7 rounded-lg object-cover" />
            <span className="text-lg font-semibold tracking-tight text-ink">ViralShorts</span>
          </a>
          <nav aria-label="Menu" className="hidden md:flex items-center gap-6 text-sm">
            <a href="#features" className={linkCls}>{t('land.nav.features')}</a>
            <a href="#how-it-works" className={linkCls}>{t('land.nav.how')}</a>
            <a href="#plans" className={linkCls}>{t('land.nav.pricing')}</a>
            <a href="#faq" className={linkCls}>{t('land.nav.faq')}</a>
          </nav>
          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            <button type="button" onClick={() => setLang(lang === 'vi' ? 'en' : 'vi')}
              className="px-2.5 py-1.5 rounded-full text-xs text-muted hover:text-ink hover:bg-paper3 transition-colors">
              {t('lang.switch')}
            </button>
            <ThemeButton t={t} />
            {!isSignedIn && (
              <a href="#/login" className="hidden sm:inline-flex px-3 py-2 text-sm text-ink2 hover:text-ink no-underline">{t('lp.foot.signin')}</a>
            )}
            <button type="button" onClick={onLaunchApp} className="btn-primary !px-4 !py-2 whitespace-nowrap shrink-0">{t('land.open')}</button>
          </div>
        </div>
      </header>

      <main>
        {/* hero: the start box is the first interactive thing on the page */}
        <section className="relative overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-[28rem] pointer-events-none opacity-60"
            style={{ background: 'radial-gradient(60% 70% at 50% 0%, oklch(var(--c-brass) / 0.18), transparent 70%)' }} aria-hidden="true" />
          <div className="relative max-w-4xl mx-auto px-4 sm:px-6 pt-14 sm:pt-24 pb-12 text-center">
            <span className="chip"><Sparkles size={14} className="text-brass" /> {t('lp.hero.eyebrow')}</span>
            <h1 className="font-display text-4xl sm:text-6xl lg:text-7xl leading-[1.06] mt-6">
              {t('lp.hero.title.a')} <span className="text-gradient">{t('lp.hero.title.b')}</span>
            </h1>
            <p className="mt-6 text-base sm:text-lg leading-relaxed text-ink2 max-w-2xl mx-auto">{t('lp.hero.sub')}</p>
            <div className="mt-9"><StartBox t={t} onLaunchApp={onLaunchApp} /></div>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
              <span className="text-xs text-muted mr-1">{t('lp.for')}</span>
              {PLATFORMS.map((p) => <span key={p} className="chip !text-xs">{p}</span>)}
            </div>
          </div>
        </section>

        {/* showcase: demo area with a pill tab bar */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-24" aria-labelledby="showcase-title">
          <h2 id="showcase-title" className="sr-only">{t('lp.showcase.title')}</h2>
          <div className="card !rounded-[24px] p-2 sm:p-3 shadow-pop">
            <div className="flex gap-1 overflow-x-auto custom-scrollbar p-1 rounded-2xl bg-paper3/60" role="tablist" aria-label={t('lp.showcase.title')}>
              {TABS.map((item) => {
                const TabIcon = item.icon;
                const on = tab === item.id;
                return (
                  <button key={item.id} type="button" role="tab" id={`tab-${item.id}`} aria-selected={on} aria-controls="showcase-panel" onClick={() => setTab(item.id)}
                    className={`shrink-0 flex items-center gap-2 px-4 py-2 rounded-xl text-sm transition-colors ${
                      on ? 'bg-paper text-ink shadow-card font-medium' : 'text-muted hover:text-ink'}`}>
                    <TabIcon size={15} /> {t(`land.tab.${item.id}`)}
                  </button>
                );
              })}
            </div>
            <div id="showcase-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="grid md:grid-cols-2 gap-8 items-center p-4 sm:p-10">
              <DemoSlot tab={tab} t={t} />
              <div>
                <h3 className="font-display text-3xl sm:text-4xl leading-tight">{t(`land.tab.${tab}.title`)}</h3>
                <p className="mt-4 text-ink2 leading-relaxed">{t(`land.tab.${tab}.desc`)}</p>
                <button type="button" onClick={onLaunchApp} className="btn-primary mt-6">{t('land.cta')} <ArrowRight size={16} /></button>
              </div>
            </div>
          </div>
        </section>

        {/* how it works */}
        <section id="how-it-works" className="border-t border-rule">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
            <Eyebrow>{t('lp.how.eyebrow')}</Eyebrow>
            <h2 className="font-display text-3xl sm:text-4xl max-w-2xl mt-2">{t('land.how.title')}</h2>
            <ol className="mt-10 grid md:grid-cols-3 gap-5 list-none p-0">
              {STEPS.map((s, i) => {
                const StepIcon = STEP_ICONS[i];
                return (
                  <li key={s} className="card card-hover p-6">
                    <div className="flex items-center justify-between">
                      <span className="inline-flex w-10 h-10 rounded-xl bg-brand text-brassink items-center justify-center shadow-cta"><StepIcon size={18} /></span>
                      <span className="font-display text-4xl text-gradient tabular-nums" aria-hidden="true">{i + 1}</span>
                    </div>
                    <h3 className="mt-5 text-lg font-medium text-ink">{t(`land.${s}.title`)}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-ink2">{t(`land.${s}.desc`)}</p>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        {/* features */}
        <section id="features" className="border-t border-rule bg-paper2/40">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
            <Eyebrow>{t('lp.feat.eyebrow')}</Eyebrow>
            <h2 className="font-display text-3xl sm:text-4xl max-w-2xl mt-2">{t('land.feat.title')}</h2>
            <p className="mt-4 text-ink2 max-w-2xl">{t('lp.feat.sub')}</p>
            <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {FEATURES.map((item) => {
                const FeatIcon = item.icon;
                return (
                  <div key={item.k} className="card card-hover p-6">
                    <span className="inline-flex w-11 h-11 rounded-xl bg-brass/10 text-brass items-center justify-center"><FeatIcon size={20} /></span>
                    <h3 className="mt-4 font-medium text-ink">{t(`land.${item.k}.title`)}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-ink2">{t(`land.${item.k}.desc`)}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* explainable score */}
        <section className="border-t border-rule">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-24 grid md:grid-cols-2 gap-10 items-center">
            <div>
              <Eyebrow>{t('lp.score.eyebrow')}</Eyebrow>
              <h2 className="font-display text-3xl sm:text-4xl leading-tight mt-2">{t('land.score.title')}</h2>
              <p className="mt-4 text-ink2 leading-relaxed">{t('land.score.desc')}</p>
            </div>
            <div className="card p-6 space-y-3">
              <span className="chip !py-0.5 !px-2.5 !text-xs">{t('lp.score.sample')}</span>
              {[['hook', 92], ['pace', 100], ['silence', 71], ['length', 100]].map(([k, v]) => (
                <div key={k}>
                  <div className="flex justify-between text-xs text-ink2 mb-1"><span>{t(`viral.signal.${k}`)}</span><span className="tabular-nums">{v}</span></div>
                  <div className="h-1.5 rounded-full bg-paper3 overflow-hidden"><div className="h-full rounded-full bg-brand" style={{ width: `${v}%` }} /></div>
                </div>
              ))}
              <p className="pt-2 text-xs text-muted">{t('land.score.note')}</p>
            </div>
          </div>
        </section>

        <PricingTeaser t={t} lang={lang} />

        {/* faq */}
        <section id="faq" className="border-t border-rule">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
            <Eyebrow>{t('lp.faq.eyebrow')}</Eyebrow>
            <h2 className="font-display text-3xl sm:text-4xl mt-2">{t('land.faq.title')}</h2>
            <Faq t={t} />
          </div>
        </section>

        {/* closing call to action */}
        <section className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-24">
          <div className="card !rounded-[28px] px-6 py-14 sm:py-20 text-center relative overflow-hidden">
            <div className="absolute -top-24 -right-16 w-72 h-72 rounded-full opacity-40 blur-2xl" style={{ background: ORBS.clips }} aria-hidden="true" />
            <div className="absolute -bottom-28 -left-10 w-72 h-72 rounded-full opacity-30 blur-2xl" style={{ background: ORBS.dub }} aria-hidden="true" />
            <div className="relative">
              <h2 className="font-display text-3xl sm:text-5xl max-w-2xl mx-auto leading-tight">{t('lp.end.title')}</h2>
              <p className="mt-4 text-ink2 max-w-xl mx-auto">{t('lp.end.sub')}</p>
              <div className="mt-8"><StartBox t={t} onLaunchApp={onLaunchApp} /></div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-rule bg-paper2/40">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12">
          <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
            <div>
              <a href="#landing" className="inline-flex items-center gap-2.5">
                <img src="/logo-viralshorts.png" alt="" className="w-7 h-7 rounded-lg object-cover" />
                <span className="text-lg font-semibold tracking-tight text-ink">ViralShorts</span>
              </a>
              <p className="mt-3 text-sm text-muted max-w-xs leading-relaxed">{t('lp.foot.tag')}</p>
            </div>
            <FooterColumn title={t('lp.foot.product')}>
              <li><a href="#features" className={footLink}>{t('land.nav.features')}</a></li>
              <li><a href="#how-it-works" className={footLink}>{t('land.nav.how')}</a></li>
              <li><a href="#plans" className={footLink}>{t('land.nav.pricing')}</a></li>
              <li><a href="#faq" className={footLink}>{t('land.nav.faq')}</a></li>
              {!isSignedIn && <li><a href="#/login" className={footLink}>{t('lp.foot.signin')}</a></li>}
            </FooterColumn>
            <FooterColumn title={t('lp.foot.support')}>
              {hasRealEmail
                ? <li><a href={`mailto:${SUPPORT_EMAIL}`} className={footLink}>{SUPPORT_EMAIL}</a></li>
                : <li><a href="/legal-notice" className={footLink}>{t('lp.foot.contact')}</a></li>}
              <li><a href="/report-content" className={footLink}>{t('land.contact.report')}</a></li>
              <li><a href="#/pricing" className={footLink}>{t('land.footer.pricing')}</a></li>
            </FooterColumn>
            <FooterColumn title={t('lp.foot.legal')}>
              <li><a href="/terms" className={footLink}>{t('land.footer.terms')}</a></li>
              <li><a href="/privacy" className={footLink}>{t('land.footer.privacy')}</a></li>
              <li><a href="/refunds" className={footLink}>{t('land.footer.refunds')}</a></li>
              <li><a href="/legal-notice" className={footLink}>{t('land.contact.legal')}</a></li>
              <li><button type="button" onClick={openConsentManager} className={footLink}>{t('land.footer.cookies')}</button></li>
            </FooterColumn>
          </div>
          <div className="mt-10 pt-6 border-t border-rule flex flex-wrap items-center justify-between gap-3 text-xs text-muted">
            <span>© {new Date().getFullYear()} ViralShorts. {t('lp.foot.rights')}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
