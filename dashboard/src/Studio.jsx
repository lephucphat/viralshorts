import { useEffect } from 'react';
import './i18n.studio';
import './i18n.billing';
import './i18n.account';
import './i18n.lifecycle';
import './i18n.revenue';
import './i18n.ui';
import './i18n.landing';
import './i18n.calendar';
import { useAuth } from './contexts/AuthContext';
import AuthPage from './pages/AuthPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectPage from './pages/ProjectPage';
import BrandPage from './pages/BrandPage';
import StudioAccountPage from './pages/StudioAccountPage';
import StudioPricingPage from './pages/StudioPricingPage';
import RecoveryPage from './pages/RecoveryPage';
import AdminPage from './pages/AdminPage';
import ReceiptPage from './pages/ReceiptPage';
import CalendarPage from './pages/CalendarPage';
import HelpPage from './pages/HelpPage';
import { ToolsIndex, ToolView } from './pages/ToolsPage';
import { TOOLS } from './lib/tools';
import { isStudioHash, useHash } from './lib/hashRoute';
import { referralApi } from './lib/studio';

export default function Studio() {
  const { isSignedIn } = useAuth();
  const hash = useHash();
  const path = hash.split('?')[0];
  const isAuthPage = path === '#/login' || path === '#/register';
  const isEmailLink = path === '#/forgot' || path === '#/reset' || path === '#/verify';

  // A friend's link (#/register?ref=CODE) is remembered across sign-up, then applied once signed in.
  useEffect(() => {
    const m = /[?&]ref=([A-Za-z0-9_-]{3,32})/.exec(hash);
    if (m) { try { localStorage.setItem('vs_ref', m[1]); } catch (_) { /* storage blocked */ } }
  }, [hash]);
  useEffect(() => {
    if (!isSignedIn) return;
    let code = '';
    try { code = localStorage.getItem('vs_ref') || ''; localStorage.removeItem('vs_ref'); } catch (_) { return; }
    if (code) referralApi.attach(code).catch(() => { /* not valid for this account: nothing to tell */ });
  }, [isSignedIn]);

  // Redirects are effects, never render-time navigation.
  useEffect(() => {
    if (isEmailLink) return;
    if (!isSignedIn && !isAuthPage) window.location.replace('#/login');
    else if (isSignedIn && isAuthPage) window.location.replace('#/projects');
    else if (path === '#app' || !isStudioHash(hash)) window.location.replace('#/projects');
  }, [isSignedIn, isAuthPage, isEmailLink, path, hash]);

  // Email links work whether or not a session exists.
  if (path === '#/forgot') return <RecoveryPage mode="forgot" />;
  if (path === '#/reset') return <RecoveryPage mode="reset" />;
  if (path === '#/verify') return <RecoveryPage mode="verify" />;

  if (!isSignedIn) return isAuthPage ? <AuthPage key={hash} mode={path === '#/register' ? 'register' : 'login'} /> : null;
  if (isAuthPage || path === '#app' || !isStudioHash(hash)) return null;

  if (path.startsWith('#/project/')) {
    const jobId = decodeURIComponent(path.slice('#/project/'.length));
    return <ProjectPage key={jobId} jobId={jobId} />;
  }
  if (path.startsWith('#/receipt/')) return <ReceiptPage key={path} paymentId={decodeURIComponent(path.slice('#/receipt/'.length))} />;
  if (path === '#/brand') return <BrandPage />;
  if (path === '#/calendar') return <CalendarPage />;
  if (path === '#/help' || path.startsWith('#/help/') || path === '#/changelog') return <HelpPage key={path} path={path} />;
  if (path === '#/account') return <StudioAccountPage />;
  if (path === '#/pricing') return <StudioPricingPage />;
  if (path === '#/admin') return <AdminPage />;
  if (path.startsWith('#/tools/')) {
    const [tool, draft] = path.slice('#/tools/'.length).split('/');
    if (TOOLS.some((x) => x.id === tool)) return <ToolView key={`${tool}/${draft || ''}`} tool={tool} draft={draft || null} />;
    return <ToolsIndex />;
  }
  if (path === '#/tools') return <ToolsIndex />;
  return <ProjectsPage />;
}
