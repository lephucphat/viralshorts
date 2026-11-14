import { StrictMode, useState, useEffect, lazy, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './i18n.studio'
import './i18n.account'
import './i18n.billing'
import './i18n.revenue'
import './i18n.ui'
import './i18n.calendar'
import './i18n.landing'
import Landing from './Landing.jsx'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { Loader2 } from 'lucide-react'
import { LangProvider, useLang } from './contexts/LangContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { capture as captureAttribution } from './lib/attribution'
import PricingPage from './components/PricingPage'
import AccountPage from './components/AccountPage'
import LoginModal from './components/LoginModal'
import { applyConsent } from './lib/consent'
import { isStudioHash, useHash } from './lib/hashRoute'
import CookieBanner from './components/CookieBanner'

const App = lazy(() => import('./App.jsx'))
const Studio = lazy(() => import('./Studio.jsx'))
const Legal = lazy(() => import('./Legal.jsx'))
const OAuthConsent = lazy(() => import('./components/OAuthConsent'))

function PageShell({ title, children }) {
  return (
    <div className="min-h-screen bg-paper text-ink2">
      <header className="h-14 sm:h-16 border-b border-rule bg-paper flex items-center justify-between gap-3 px-4 sm:px-6 sticky top-0 z-20">
        <a href="#app" className="font-display lowercase text-lg text-ink truncate">ViralShorts</a>
        <a href="#app" className="text-sm lowercase text-muted hover:text-ink transition-colors shrink-0">← <span className="hidden sm:inline">Back to app</span><span className="sm:hidden">back</span></a>
      </header>
      <main className="p-4 sm:p-6 md:p-8 pb-[max(2rem,env(safe-area-inset-bottom))]">
        {title && <h1 className="font-display lowercase text-2xl sm:text-3xl text-ink text-center mb-6 sm:mb-10">{title}</h1>}
        {children}
      </main>
    </div>
  );
}

function PricingView() {
  const [showLogin, setShowLogin] = useState(false);
  return (
    <PageShell>
      <PricingPage onRequireLogin={() => setShowLogin(true)} />
      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </PageShell>
  );
}

function AccountView() {
  const { isSignedIn, loading } = useAuth();
  useEffect(() => {
    if (!loading && !isSignedIn) window.location.hash = '#/pricing';
  }, [loading, isSignedIn]);
  return <PageShell><AccountPage /></PageShell>;
}

// Landing spot after an account is erased. Its own view because the session is
// gone: sending the user to #/account would bounce them to pricing with no
// explanation, and "viralshorts_skip_landing" would send them into the app.
function DeletedView() {
  const { t } = useLang();
  return (
    <div className="min-h-screen bg-paper text-ink2 flex items-center justify-center p-6">
      <div className="max-w-md text-center space-y-4">
        <h1 className="font-display text-2xl sm:text-3xl text-ink">{t('deleted.title')}</h1>
        <p className="text-sm">{t('deleted.body')}</p>
        <p className="text-sm text-muted">{t('deleted.welcome')}</p>
        <a href="#landing" className="btn-ghost px-4 py-2 inline-flex">{t('deleted.back')}</a>
      </div>
    </div>
  );
}

// Own accounts (ACCOUNTS_ENABLED): the product. Signed-in visitors live in the
// studio; the landing page stays for first contact, the legal page and the
// "your account is deleted" farewell.
function SigningIn() {
  const { t } = useLang();
  return (
    <div className="min-h-screen bg-paper flex items-center justify-center gap-3 text-muted text-sm" role="status">
      <Loader2 size={18} className="animate-spin" /> {t('auth.signingin')}
    </div>
  );
}

function AccountsRoot() {
  const { isSignedIn } = useAuth();
  const hash = useHash();
  const launch = () => {
    window.location.hash = isSignedIn ? '#/projects' : '#/register';
  };
  // An empty hash is the front door: everyone sees the marketing page first, signed in or
  // not (the header button opens the library). Sign-in and OAuth return to #/projects
  // explicitly, so nothing depends on skipping this page.
  if (hash === '#legal') return <Legal />;
  if (hash.startsWith('#/deleted')) return <DeletedView />;
  // Google hands the browser back here; AuthContext consumes the token and moves on.
  if (hash.startsWith('#/auth/')) return <SigningIn />;
  if (isStudioHash(hash)) return <Studio />;
  return <Landing onLaunchApp={launch} />;
}

function Root() {
  const { accountsEnabled, loading } = useAuth();
  if (loading) {
    return <div className="min-h-screen bg-paper flex items-center justify-center text-muted text-sm">…</div>;
  }
  return accountsEnabled ? <AccountsRoot /> : <ClassicRoot />;
}

function ClassicRoot() {
  const resolveView = () => {
    const hash = window.location.hash || '';
    if (hash.startsWith('#/auth/')) return 'auth';       // AuthContext consumes then redirects
    if (hash.startsWith('#/oauth/authorize')) return 'oauth';
    if (hash.startsWith('#/account')) return 'account';
    if (hash.startsWith('#/deleted')) return 'deleted';
    if (hash.startsWith('#/pricing')) return 'pricing';
    if (hash === '#legal') return 'legal';
    // #landing = explicit landing view (app logo); section anchors keep the landing mounted
    if (['#landing', '#features', '#how-it-works', '#pricing', '#comparison', '#faq'].includes(hash)) return 'landing';
    // First visit sees the landing page; "Open app" remembers the choice.
    if (hash === '#app' || hash.startsWith('#app?') || localStorage.getItem('viralshorts_skip_landing') === '1') return 'app';
    return 'landing';
  };

  const [view, setView] = useState(resolveView);

  useEffect(() => {
    const handleHashChange = () => setView(resolveView());
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleLaunchApp = () => {
    localStorage.setItem('viralshorts_skip_landing', '1');
    window.location.hash = '#app';
    setView('app');
  };

  if (view === 'legal') return <Legal />;
  if (view === 'pricing') return <PricingView />;
  if (view === 'account') return <AccountView />;
  if (view === 'oauth') return <OAuthConsent />;
  if (view === 'deleted') return <DeletedView />;
  if (view === 'auth') {
    return <div className="min-h-screen flex items-center justify-center bg-background text-zinc-400">Signing you in…</div>;
  }
  if (view === 'app') return <App />;
  return <Landing onLaunchApp={handleLaunchApp} />;
}

// Before React mounts: AuthContext rewrites the URL on auth redirects, which
// would destroy the referrer and any UTM params we still need to read.
captureAttribution();

// Start whatever the visitor previously agreed to. Nothing at all on a first
// visit: index.html only publishes the analytics initialiser, it never runs it.
applyConsent();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
    <LangProvider>
      <AuthProvider>
        <Suspense fallback={<div className="min-h-screen bg-paper flex items-center justify-center text-muted text-sm lowercase">loading…</div>}>
          <Root />
        </Suspense>
        <CookieBanner />
      </AuthProvider>
    </LangProvider>
    </ThemeProvider>
  </StrictMode>,
)
