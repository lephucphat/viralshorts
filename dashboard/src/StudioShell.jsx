import { CalendarDays, LifeBuoy, FolderOpen, Palette, Youtube, UserRound, Moon, Sun, Monitor, Globe, LogOut, ShieldCheck, Plus, Gem, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { recoveryApi } from './lib/studio';
import { useAuth } from './contexts/AuthContext';
import { errorMessage } from './lib/errors';
import { useLang } from './contexts/LangContext';
import { useTheme } from './contexts/ThemeContext';
import CreditsModalHost from './components/CreditsModalHost';
import CreateProjectModal from './components/CreateProjectModal';
import Menu from './components/ui/Menu';
import NotificationBell from './components/NotificationBell';

const NAV = [
  { id: 'projects', href: '#/projects', icon: FolderOpen, label: 'shell.projects' },
  { id: 'calendar', href: '#/calendar', icon: CalendarDays, label: 'shell.calendar' },
  { id: 'brand', href: '#/brand', icon: Palette, label: 'shell.brand' },
  { id: 'tools', href: '#/tools', icon: Youtube, label: 'shell.tools' },
  { id: 'pricing', href: '#/pricing', icon: Gem, label: 'shell.pricing' },
  { id: 'account', href: '#/account', icon: UserRound, label: 'shell.account' },
  { id: 'help', href: '#/help', icon: LifeBuoy, label: 'shell.help', desktopOnly: true },   // phones reach it from the top bar
];

const THEME_NEXT = { light: 'dark', dark: 'system', system: 'light' };

function UsageMeter() {
  const { usage } = useAuth();
  const { t } = useLang();
  if (!usage) return null;
  if (usage.unlimited) {
    return <p className="readout px-3">{t('shell.usage.unlimited', { used: usage.used })}</p>;
  }
  if (usage.paid) {
    // Paid edition: show what is LEFT (credits), and a way to buy more.
    const left = usage.remaining;
    const low = left <= Math.max(5, usage.limit * 0.1);
    return (
      <div className="px-3 py-2" title={t('billing.shell.tip')}>
        <div className="flex items-baseline justify-between text-xs">
          <span className="text-muted">{t('billing.shell.credits')}</span>
          <span className={`readout ${low ? '!text-warn' : ''}`}>{left}</span>
        </div>
        <div className="h-1.5 mt-1.5 rounded-full bg-paper3 overflow-hidden">
          <div className={`h-full rounded-full ${low ? 'bg-warn' : 'bg-brass'}`}
            style={{ width: `${Math.min(100, Math.round((left / Math.max(1, usage.limit)) * 100))}%` }} />
        </div>
        {(usage.plan === 'free' || low) && (
          <a href="#/pricing" className="mt-3 block rounded-xl bg-brand text-brassink p-3 shadow-cta hover:brightness-110 transition">
            <span className="flex items-center gap-1.5 text-sm font-semibold"><Sparkles size={14} /> {t('shell.upgrade.title')}</span>
            <span className="block text-xs opacity-90 mt-1 leading-snug">{t('shell.upgrade.text')}</span>
            <span className="block text-xs font-semibold mt-2 underline underline-offset-2">{t('shell.upgrade.cta')}</span>
          </a>
        )}
      </div>
    );
  }
  const pct = Math.min(100, Math.round((usage.used / Math.max(1, usage.limit)) * 100));
  const low = usage.remaining <= Math.max(5, usage.limit * 0.1);
  return (
    <div className="px-3 py-2" title={t('shell.usage.tip')}>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted">{t('shell.usage')}</span>
        <span className={`readout ${low ? '!text-warn' : ''}`}>{usage.used}/{usage.limit}</span>
      </div>
      <div className="h-1.5 mt-1.5 rounded-full bg-paper3 overflow-hidden">
        <div className={`h-full rounded-full ${low ? 'bg-warn' : 'bg-brass'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Shown while the server withholds free credits until the inbox is proven.
function VerifyBanner() {
  const { t } = useLang();
  const { user, verificationRequired, refreshMe } = useAuth();
  const [state, setState] = useState({ busy: false, msg: '', bad: false });
  if (!user || !verificationRequired || user.email_verified) return null;

  const resend = async () => {
    setState({ busy: true, msg: '', bad: false });
    try {
      const res = await recoveryApi.resend();
      if (res?.sent === false) {
        // The server did not send anything: say why instead of claiming it did.
        if (res.reason === 'already_verified') {
          setState({ busy: false, msg: t('verify.already'), bad: false });
          await refreshMe();            // the banner has no reason to stay
        } else {
          setState({ busy: false, msg: t(res.reason === 'mail_off' ? 'verify.mail_off' : 'auth.err.generic'), bad: true });
        }
        return;
      }
      setState({ busy: false, msg: t('verify.resent'), bad: false });
    } catch (e) {
      setState({ busy: false, msg: errorMessage(t, e), bad: true });
    }
  };
  return (
    <div role="status" className="shrink-0 bg-warn/10 text-ink2 text-sm px-4 sm:px-8 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-1">
      <span>{t('verify.banner', { email: user.email })}</span>
      <button type="button" onClick={resend} disabled={state.busy} className="underline underline-offset-4 text-ink font-medium disabled:opacity-60">
        {t('verify.resend')}
      </button>
      {state.msg && <span className={state.bad ? 'text-danger' : 'text-ok'}>{state.msg}</span>}
    </div>
  );
}

// The product frame: a rail on desktop, a bottom bar on phones. Pages render
// inside it and own their own heading, so the frame never needs to know them.
function CreditChip() {
  const { usage } = useAuth();
  const { t } = useLang();
  if (!usage?.paid || usage.unlimited) return null;
  const low = usage.remaining <= Math.max(5, usage.limit * 0.1);
  return (
    <a href="#/pricing" title={t('shell.credits.tip')}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${low ? 'border-warn/50 text-warn bg-warn/10' : 'border-rule-2 text-ink2 hover:border-brass/50 hover:bg-paper2'}`}>
      <Gem size={14} className={low ? '' : 'text-brass'} /> {t('shell.credits.chip', { n: usage.remaining })}
    </a>
  );
}

function AccountMenu({ onSignOut }) {
  const { t, lang, setLang } = useLang();
  const { mode, setMode } = useTheme();
  const { user } = useAuth();
  const ThemeIcon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor;
  const initial = (user?.name || user?.email || '?').trim().charAt(0).toUpperCase();
  const go = (hash) => () => { window.location.hash = hash; };
  return (
    <Menu
      trigger={(props) => (
        <button type="button" {...props} aria-label={t('shell.menu')} title={user?.email}
          className="w-9 h-9 rounded-full bg-brand text-brassink text-sm font-semibold flex items-center justify-center shadow-card hover:brightness-110 transition">
          {initial}
        </button>
      )}
      items={[
        { id: 'account', label: t('shell.account'), icon: <UserRound size={15} />, onSelect: go('#/account') },
        user?.is_admin && { id: 'admin', label: t('admin.nav'), icon: <ShieldCheck size={15} />, onSelect: go('#/admin') },
        { id: 'theme', label: t(`theme.${mode}`), icon: <ThemeIcon size={15} />, onSelect: () => setMode(THEME_NEXT[mode] || 'light') },
        { id: 'lang', label: t('lang.switch'), icon: <Globe size={15} />, onSelect: () => setLang(lang === 'vi' ? 'en' : 'vi') },
        { id: 'out', label: t('shell.signout'), icon: <LogOut size={15} />, danger: true, onSelect: onSignOut },
      ]}
    />
  );
}

export default function StudioShell({ active, children, wide = false, fill = false }) {
  const { t, lang, setLang } = useLang();
  const { mode, setMode } = useTheme();
  const { user, logout } = useAuth();
  const [creating, setCreating] = useState(false);
  const ThemeIcon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor;
  // The console only appears for operators; the server still answers 404 to anyone else.
  const nav = user?.is_admin
    ? [...NAV, { id: 'admin', href: '#/admin', icon: ShieldCheck, label: 'admin.nav' }]
    : NAV;

  const signOut = () => {
    logout();
    window.location.hash = '#landing';
  };

  return (
    <div className="flex h-screen supports-[height:100dvh]:h-[100dvh] bg-paper overflow-hidden">
      <CreditsModalHost />
      <CreateProjectModal isOpen={creating} onClose={() => setCreating(false)} initialUrl="" initialFile={null} />
      <aside className="hidden md:flex w-60 shrink-0 flex-col bg-paper2 border-r border-rule">
        <a href="#/projects" className="px-5 h-16 flex items-center gap-2.5">
          <img src="/logo-viralshorts.png" alt="" className="w-8 h-8 rounded-input border border-rule" />
          <span className="text-lg font-semibold tracking-tight text-ink">ViralShorts</span>
        </a>
        <nav className="flex-1 px-3 py-2 space-y-1" aria-label={t('app.nav.aria')}>
          {nav.map((item) => {
            const { id, href, label } = item;
            const Icon = item.icon;
            const on = active === id;
            return (
              <a key={id} href={href} aria-current={on ? 'page' : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-full text-sm transition-colors ${on ? 'bg-paper3 text-ink font-medium' : 'text-muted hover:text-ink hover:bg-paper3/60'}`}>
                <Icon size={18} className={on ? 'text-brass' : ''} />
                {t(label)}
              </a>
            );
          })}
        </nav>
        <div className="border-t border-rule py-3">
          <UsageMeter />
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden h-14 px-4 flex items-center justify-between border-b border-rule bg-paper shrink-0">
          <a href="#/projects" className="flex items-center gap-2 min-w-0">
            <img src="/logo-viralshorts.png" alt="" className="w-7 h-7 rounded-input border border-rule" />
            <span className="text-base font-semibold text-ink">ViralShorts</span>
          </a>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => setCreating(true)} aria-label={t('shell.create')}
              className="w-9 h-9 rounded-full bg-brand text-brassink flex items-center justify-center shadow-cta"><Plus size={18} /></button>
            <NotificationBell />
            <a href="#/help" aria-label={t('shell.help')} className="p-2 rounded-full text-muted active:bg-paper3"><LifeBuoy size={17} /></a>
            <button type="button" onClick={() => setMode(THEME_NEXT[mode] || 'light')} aria-label={t('theme.tip')}
              className="p-2 rounded-full text-muted active:bg-paper3"><ThemeIcon size={17} /></button>
            <button type="button" onClick={() => setLang(lang === 'vi' ? 'en' : 'vi')} aria-label={t('lang.switch')}
              className="p-2 rounded-full text-muted active:bg-paper3"><Globe size={17} /></button>
          </div>
        </header>

        <header className="hidden md:flex h-16 shrink-0 items-center justify-end gap-3 px-8 border-b border-rule bg-paper">
          <CreditChip />
          <NotificationBell />
          <button type="button" onClick={() => setCreating(true)} className="btn-primary !py-2 !px-5">
            <Plus size={16} /> {t('shell.create')}
          </button>
          <AccountMenu onSignOut={signOut} />
        </header>

        <VerifyBanner />
        {fill ? (
          // A page that manages its own scrolling (the project workspace).
          <main className="flex-1 min-h-0 flex flex-col overflow-hidden">{children}</main>
        ) : (
          <main className="flex-1 overflow-y-auto custom-scrollbar">
            <div className={`mx-auto w-full px-4 sm:px-8 py-6 sm:py-10 ${wide ? 'max-w-[88rem]' : 'max-w-6xl'}`}>
              {children}
            </div>
          </main>
        )}

        <nav className="md:hidden shrink-0 border-t border-rule bg-paper2/95 backdrop-blur-sm safe-bottom" aria-label={t('app.nav.aria')}>
          <div className="flex">
            {nav.filter((item) => !item.desktopOnly).map((item) => {
              const { id, href, label } = item;
              const Icon = item.icon;
              const on = active === id;
              return (
                <a key={id} href={href} aria-current={on ? 'page' : undefined}
                  className={`flex-1 min-w-0 flex flex-col items-center justify-center gap-1 py-2 min-h-[56px] ${on ? 'text-ink' : 'text-muted'}`}>
                  <Icon size={19} className={on ? 'text-brass' : ''} />
                  <span className="text-[0.65625rem] leading-none truncate max-w-full px-0.5">{t(label)}</span>
                </a>
              );
            })}
          </div>
        </nav>
      </div>
    </div>
  );
}
