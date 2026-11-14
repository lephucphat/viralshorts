import { useEffect, useState } from 'react';

// Hash routes of the product (own accounts). Anything else under the studio
// falls back to the projects page, so a stale bookmark never lands on a blank screen.
export const STUDIO_PREFIXES = ['#/login', '#/register', '#/projects', '#/project/', '#/brand', '#/account', '#/pricing', '#/tools',
  '#/forgot', '#/reset', '#/verify', '#/admin', '#/receipt/', '#/calendar', '#/help', '#/changelog'];

export function isStudioHash(hash) {
  return hash === '#app' || hash.startsWith('#app?') || STUDIO_PREFIXES.some((p) => hash.startsWith(p));
}

export function useHash() {
  const [hash, setHash] = useState(() => window.location.hash || '');
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || '');
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return hash;
}
