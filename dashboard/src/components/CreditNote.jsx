import { useLang } from '../contexts/LangContext';
import { useCosts } from '../lib/useCosts';

// "Costs 3 credits" next to a button that spends credits. Renders nothing when the edition
// has no credits or the price list has not arrived, so it is safe to drop in anywhere.
export default function CreditNote({ cost, perMinute = false, className = 'text-xs text-muted' }) {
  const { t } = useLang();
  const costs = useCosts();
  const n = costs?.[cost];
  if (n == null) return null;
  return <span className={className}>{t(perMinute ? 'credits.note.minute' : 'credits.note', { n })}</span>;
}
