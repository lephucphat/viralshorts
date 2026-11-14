import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

// Three choices the user can make; the effective theme is always 'light' or
// 'dark'. 'system' follows the OS and updates live when the OS flips.
const THEME_MODES = ['light', 'dark', 'system'];
const STORAGE_KEY = 'vs_theme';
// New visitors get the light theme; anyone who picked a mode keeps it.
const DEFAULT_MODE = 'light';

const ThemeContext = createContext({
  mode: DEFAULT_MODE,
  theme: 'light',
  setMode: () => {},
});

function readStoredMode() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (THEME_MODES.includes(stored)) return stored;
  } catch (_) { /* private mode: use the default */ }
  return DEFAULT_MODE;
}

function systemTheme() {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch (_) {
    return 'light';
  }
}

// Keep in sync with the inline script in index.html, which runs before first
// paint so a dark-mode user never sees a white flash.
function applyTheme(theme) {
  const root = document.documentElement;
  root.setAttribute('data-theme', theme);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#0c0b0a' : '#fdfcfc');
  const scheme = document.querySelector('meta[name="color-scheme"]');
  if (scheme) scheme.setAttribute('content', theme);
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readStoredMode);
  const [system, setSystem] = useState(systemTheme);

  useEffect(() => {
    let mq;
    try { mq = window.matchMedia('(prefers-color-scheme: dark)'); } catch (_) { return undefined; }
    const onChange = () => setSystem(mq.matches ? 'dark' : 'light');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const theme = mode === 'system' ? system : mode;

  useEffect(() => { applyTheme(theme); }, [theme]);

  const setMode = useCallback((next) => {
    if (!THEME_MODES.includes(next)) return;
    setModeState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch (_) { /* best effort */ }
  }, []);

  const value = useMemo(() => ({ mode, theme, setMode }), [mode, theme, setMode]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
