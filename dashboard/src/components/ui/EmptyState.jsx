/**
 * Friendly empty state: icon, title, one line of help and an optional action.
 * Props: icon (node), title, text, action (node), compact (less padding).
 */
export default function EmptyState({ icon, title, text, action, compact = false }) {
  return (
    <div className={`empty-state ${compact ? '!py-8' : ''}`}>
      {icon && (
        <span className="w-12 h-12 rounded-2xl bg-brand text-brassink flex items-center justify-center shadow-cta" aria-hidden="true">
          {icon}
        </span>
      )}
      {title && <h3 className="font-display text-xl text-ink">{title}</h3>}
      {text && <p className="text-sm text-muted max-w-md">{text}</p>}
      {action}
    </div>
  );
}
