import { useEffect, useState } from 'react';
import Modal from './ui/Modal';
import { useLang } from '../contexts/LangContext';
import { CREDITS_NEEDED_EVENT } from '../lib/api';

// One prompt for the whole product: any request the server answers with 402 (not enough
// credits, or a feature the plan does not include) lands here, whichever screen sent it.
export default function CreditsModalHost() {
  const { t } = useLang();
  const [hit, setHit] = useState(null);

  useEffect(() => {
    const onHit = (e) => setHit(e.detail || {});
    window.addEventListener(CREDITS_NEEDED_EVENT, onHit);
    return () => window.removeEventListener(CREDITS_NEEDED_EVENT, onHit);
  }, []);

  // Moving to another page ends the prompt (the pricing link below does exactly that).
  useEffect(() => {
    const close = () => setHit(null);
    window.addEventListener('hashchange', close);
    return () => window.removeEventListener('hashchange', close);
  }, []);

  if (!hit) return null;
  const plan = hit.needsPlan;
  const known = hit.creditsRequired != null;
  return (
    <Modal isOpen onClose={() => setHit(null)} size="sm"
      title={t(plan ? 'credits.modal.plan.title' : 'billing.quota.title')}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-quiet px-4 py-2" onClick={() => setHit(null)}>{t('credits.modal.later')}</button>
          <a href="#/pricing" className="btn-primary px-5 py-2">{t(plan ? 'billing.account.upgrade' : 'billing.quota.cta')}</a>
        </div>
      )}>
      <p className="text-sm text-ink2">
        {plan ? t('billing.plan_required')
          : known ? t('billing.quota.body', { required: hit.creditsRequired, remaining: hit.creditsRemaining ?? 0 })
            : t('create.err.quota')}
      </p>
      {!plan && <p className="text-xs text-muted mt-3">{t('credits.modal.promo')}</p>}
    </Modal>
  );
}
