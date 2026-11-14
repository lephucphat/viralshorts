import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_LANG, LANGS, translate } from '../i18n';

const STORAGE_KEY = 'vs_lang';

const LangContext = createContext({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (key, vars) => translate(DEFAULT_LANG, key, vars),
});

function readStoredLang() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (LANGS.includes(stored)) return stored;
  } catch (_) { /* private mode: fall through to the default */ }
  return DEFAULT_LANG;
}

// eslint-disable-next-line react-refresh/only-export-components
export const useLang = () => useContext(LangContext);

// eslint-disable-next-line react-refresh/only-export-components
export const useT = () => useContext(LangContext).t;

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(readStoredLang);

  const setLang = useCallback((next) => {
    if (!LANGS.includes(next)) return;
    setLangState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch (_) { /* best effort */ }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo(() => ({
    lang,
    setLang,
    t: (key, vars) => translate(lang, key, vars),
  }), [lang, setLang]);

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}
