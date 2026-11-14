import { ArrowRight } from 'lucide-react';
import StudioShell from '../StudioShell';
import App from '../App';
import { useLang } from '../contexts/LangContext';
import { TOOLS } from '../lib/tools';
import ToolDrafts from '../components/ToolDrafts';
import SavedThumbnails from '../components/SavedThumbnails';

export function ToolsIndex() {
  const { t } = useLang();
  return (
    <StudioShell active="tools">
      <h1 className="font-display text-3xl text-ink">{t('tools.title')}</h1>
      <p className="text-muted mt-1.5 mb-8 max-w-xl">{t('tools.sub')}</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {TOOLS.map((tool) => {
          const { id, name, desc } = tool;
          const Icon = tool.icon;
          return (
          <a key={id} href={`#/tools/${id}`} className="card card-hover p-6 block group">
            <span className="w-11 h-11 rounded-input bg-paper3 flex items-center justify-center mb-4">
              <Icon size={20} className="text-brass" />
            </span>
            <h2 className="text-base font-medium text-ink">{t(name)}</h2>
            <p className="text-sm text-muted mt-1.5">{t(desc)}</p>
            <span className="inline-flex items-center gap-1.5 text-sm text-ink mt-4">
              {t('tools.open')} <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
            </span>
          </a>
          );
        })}
      </div>
      <ToolDrafts />
      <SavedThumbnails />
    </StudioShell>
  );
}

export function ToolView({ tool, draft = null }) {
  return (
    <StudioShell active="tools" fill>
      <div className="flex-1 min-h-0">
        <App key={tool} embedded initialTab={tool} initialDraft={draft} />
      </div>
    </StudioShell>
  );
}
