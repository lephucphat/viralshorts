import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Mail, Search, Sparkles } from 'lucide-react';
import StudioShell from '../StudioShell';
import EmptyState from '../components/ui/EmptyState';
import { useLang } from '../contexts/LangContext';
import { helpApi } from '../lib/studio';
import { HELP_ARTICLES, HELP_UPDATED, inlineParts, searchArticles } from '../../seo/help.js';
import { CHANGELOG } from '../../seo/changelog.js';

// Articles link with static addresses ("/help/credit", "/#/pricing"). Inside the app a
// help/hash address becomes a plain hash link; the legal pages stay normal page loads.
function appHref(href) {
  if (href.startsWith('/#/')) return href.slice(1);
  if (href === '/help' || href.startsWith('/help/') || href === '/changelog') return `#${href}`;
  return href;
}

function Inline({ text }) {
  return inlineParts(text).map((x, i) => {
    if (x.bold) return <strong key={i} className="text-ink font-semibold">{x.bold}</strong>;
    if (x.href) return <a key={i} href={appHref(x.href)} className="text-accent underline underline-offset-2">{x.text}</a>;
    return <span key={i}>{x.text}</span>;
  });
}

function Blocks({ blocks }) {
  return (
    <div className="space-y-4 text-[0.9375rem] leading-relaxed text-ink2">
      {blocks.map((b, i) => {
        if (b.h) return <h2 key={i} className="font-display text-xl text-ink pt-3">{b.h}</h2>;
        if (b.p) return <p key={i}><Inline text={b.p} /></p>;
        if (b.ul) return <ul key={i} className="list-disc pl-5 space-y-1.5">{b.ul.map((li, j) => <li key={j}><Inline text={li} /></li>)}</ul>;
        if (b.ol) return <ol key={i} className="list-decimal pl-5 space-y-1.5">{b.ol.map((li, j) => <li key={j}><Inline text={li} /></li>)}</ol>;
        return null;
      })}
    </div>
  );
}

function Contact() {
  const { t } = useLang();
  const [email, setEmail] = useState(null);       // null while loading, '' when not configured
  useEffect(() => {
    let live = true;
    helpApi.contact().then((r) => { if (live) setEmail(r.email || ''); }).catch(() => { if (live) setEmail(''); });
    return () => { live = false; };
  }, []);
  return (
    <section className="card p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
      <div>
        <h2 className="font-display text-lg text-ink">{t('help.contact.title')}</h2>
        <p className="text-sm text-muted mt-1">{email === '' ? t('help.contact.none') : t('help.contact.text')}</p>
      </div>
      {email === null && <div className="skeleton h-10 w-44" />}
      {email && (
        <a href={`mailto:${email}`} className="btn-primary !py-2.5 !px-5 shrink-0"><Mail size={16} /> {t('help.contact.cta')}</a>
      )}
    </section>
  );
}

function Index() {
  const { t } = useLang();
  const [q, setQ] = useState('');
  const found = useMemo(() => searchArticles(q), [q]);
  return (
    <>
      <div className="mb-8">
        <h1 className="font-display text-3xl text-ink">{t('help.title')}</h1>
        <p className="text-sm text-muted mt-1">{t('help.sub')}</p>
        <label className="relative block mt-5 max-w-xl">
          <span className="sr-only">{t('help.search')}</span>
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" aria-hidden="true" />
          <input type="search" className="input-field !pl-10" value={q} placeholder={t('help.search.ph')}
            onChange={(e) => setQ(e.target.value)} />
        </label>
        {q.trim() && <p className="readout mt-3" role="status">{t('help.results', { n: found.length })}</p>}
      </div>
      {found.length === 0 ? (
        <EmptyState icon={<Search size={22} />} title={t('help.search')} text={t('help.none')} />
      ) : (
        <ul className="grid sm:grid-cols-2 gap-4">
          {found.map((a) => (
            <li key={a.slug}>
              <a href={`#/help/${a.slug}`} className="card p-5 h-full flex flex-col gap-2 hover:border-brass/50 transition-colors group">
                <span className="font-display text-lg text-ink">{a.title}</span>
                <span className="text-sm text-muted flex-1">{a.summary}</span>
                <span className="text-sm text-accent inline-flex items-center gap-1 mt-1">
                  <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <a href="#/changelog" className="card p-5 flex items-center gap-3 hover:border-brass/50 transition-colors">
          <Sparkles size={18} className="text-brass shrink-0" aria-hidden="true" />
          <span>
            <span className="block font-display text-lg text-ink">{t('help.changelog')}</span>
            <span className="block text-sm text-muted">{t('help.changelog.link')}</span>
          </span>
        </a>
        <p className="text-xs text-muted self-center">{t('help.articles.note')}</p>
      </div>
      <div className="mt-6"><Contact /></div>
    </>
  );
}

function Article({ slug }) {
  const { t, lang } = useLang();
  const article = HELP_ARTICLES.find((a) => a.slug === slug);
  if (!article) return <Index />;
  return (
    <>
      <a href="#/help" className="btn-quiet !px-3 !py-2 mb-5 inline-flex"><ArrowLeft size={15} /> {t('help.back')}</a>
      <article className="max-w-2xl">
        <h1 className="font-display text-3xl text-ink">{article.title}</h1>
        <p className="readout mt-2 !normal-case">
          {t('help.updated', { date: new Date(HELP_UPDATED).toLocaleDateString(lang, { day: 'numeric', month: 'long', year: 'numeric' }) })}
        </p>
        <div className="mt-6"><Blocks blocks={article.blocks} /></div>
      </article>
      <div className="mt-10 max-w-2xl"><Contact /></div>
    </>
  );
}

function Changelog() {
  const { t, lang } = useLang();
  return (
    <>
      <a href="#/help" className="btn-quiet !px-3 !py-2 mb-5 inline-flex"><ArrowLeft size={15} /> {t('help.back')}</a>
      <h1 className="font-display text-3xl text-ink">{t('help.changelog')}</h1>
      <p className="text-sm text-muted mt-1 mb-8">{t('help.changelog.sub')}</p>
      <ol className="space-y-6 max-w-2xl">
        {CHANGELOG.map((c) => (
          <li key={c.date} className="card p-5 sm:p-6">
            <time dateTime={c.date} className="readout !normal-case">
              {new Date(c.date).toLocaleDateString(lang, { day: 'numeric', month: 'long', year: 'numeric' })}
            </time>
            <h2 className="font-display text-xl text-ink mt-1">{c.title}</h2>
            <ul className="list-disc pl-5 mt-3 space-y-1.5 text-[0.9375rem] text-ink2">{c.items.map((i) => <li key={i}>{i}</li>)}</ul>
          </li>
        ))}
      </ol>
    </>
  );
}

export default function HelpPage({ path }) {
  let body;
  if (path === '#/changelog') body = <Changelog />;
  else if (path.startsWith('#/help/')) body = <Article slug={decodeURIComponent(path.slice('#/help/'.length))} />;
  else body = <Index />;
  return (
    <StudioShell active="help">
      {body}
    </StudioShell>
  );
}
