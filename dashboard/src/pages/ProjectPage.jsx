import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Loader2, Trash2, XCircle } from 'lucide-react';
import Modal from '../components/ui/Modal';
import StudioShell from '../StudioShell';
import App from '../App';
import { useLang } from '../contexts/LangContext';
import { projectsApi } from '../lib/studio';
import { apiFetch } from '../lib/api';

const STATUS_TONE = {
  queued: 'badge-brass', processing: 'badge-brass', completed: 'badge-ok',
  failed: 'badge-danger', cancelled: 'badge-warn',
};

// One project: a slim header from the library row, then the existing workspace
// (processing view, clip cards, editors, publishing) running on this job id.
// The id lives in the URL, so a reload lands on the same project.
export default function ProjectPage({ jobId }) {
  const { t } = useLang();
  const [project, setProject] = useState(null);
  const [missing, setMissing] = useState(false);
  const [expired, setExpired] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try { setProject(await projectsApi.get(jobId)); setMissing(false); }
    catch (e) { if (e.status === 404) setMissing(true); }
  }, [jobId]);

  useEffect(() => { setProject(null); setMissing(false); setExpired(false); refresh(); }, [refresh]);

  const active = project && (project.status === 'queued' || project.status === 'processing');

  // A finished project whose working files were swept (clips are kept for the plan's
  // retention, 1 day on Free) is unknown to the job API. Without this check the
  // workspace polls it forever and shows "waiting for its turn".
  const finished = project && !active;
  useEffect(() => {
    if (!finished) return undefined;
    let alive = true;
    apiFetch(`/api/status/${jobId}`)
      .then((res) => { if (alive && res.status === 404) setExpired(true); })
      .catch(() => {});
    return () => { alive = false; };
  }, [finished, jobId]);
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [active, refresh]);

  const confirmDelete = async () => {
    setBusy(true);
    try { await projectsApi.remove(jobId); window.location.hash = '#/projects'; }
    finally { setBusy(false); setConfirming(false); }
  };

  const cancel = async () => {
    setCancelling(true);
    try { await projectsApi.cancel(jobId); await refresh(); } finally { setCancelling(false); }
  };

  if (missing) {
    return (
      <StudioShell active="projects">
        <div className="card p-10 text-center max-w-lg mx-auto">
          <p className="text-ink font-medium">{t('project.missing')}</p>
          <a href="#/projects" className="btn-primary px-5 py-2.5 mt-5 inline-flex">{t('project.back')}</a>
        </div>
      </StudioShell>
    );
  }

  return (
    <StudioShell active="projects" fill>
      <div className="shrink-0 border-b border-rule bg-paper px-4 sm:px-6 h-14 flex items-center gap-3 min-w-0">
        <a href="#/projects" className="flex items-center gap-1.5 text-sm text-muted hover:text-ink shrink-0">
          <ArrowLeft size={16} /> <span className="hidden sm:inline">{t('project.back')}</span>
        </a>
        <span className="text-rule2" aria-hidden="true">/</span>
        <h1 className="text-sm font-medium text-ink truncate min-w-0">{project?.title || '…'}</h1>
        {project && <span className={`${STATUS_TONE[project.status] || 'badge-brass'} shrink-0`}>{t(`project.status.${project.status}`)}</span>}
        {active && (
          <button type="button" onClick={cancel} disabled={cancelling} className="btn-quiet px-3 py-1.5 text-xs ml-auto shrink-0">
            {cancelling ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} />}
            {t('project.cancel')}
          </button>
        )}
        {project && !active && (
          <button type="button" onClick={() => setConfirming(true)} className="btn-quiet px-3 py-1.5 text-xs ml-auto shrink-0 text-danger">
            <Trash2 size={14} /> {t('projects.delete')}
          </button>
        )}
      </div>
      <Modal isOpen={confirming} onClose={() => setConfirming(false)} size="sm" title={t('projects.delete.title')}
        footer={(
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-quiet px-4 py-2" onClick={() => setConfirming(false)}>{t('common.cancel')}</button>
            <button type="button" className="btn-danger px-5 py-2" disabled={busy} onClick={confirmDelete}>{t('projects.delete')}</button>
          </div>
        )}>
        <p className="text-sm text-ink2">{t('projects.delete.body', { title: project?.title || '' })}</p>
      </Modal>
      <div className="flex-1 min-h-0">
        {expired ? (
          <div className="card p-10 text-center max-w-lg mx-auto mt-10">
            <p className="text-ink font-medium">{t('project.expired.title')}</p>
            <p className="text-sm text-muted mt-2">{t('project.expired.body')}</p>
            <a href="#/projects" className="btn-primary px-5 py-2.5 mt-5 inline-flex">{t('project.back')}</a>
          </div>
        ) : (
          /* key: switching project must remount the workspace, not reuse its state */
          <App key={jobId} embedded initialJobId={jobId} startedAt={project?.created_at} />
        )}
      </div>
    </StudioShell>
  );
}
