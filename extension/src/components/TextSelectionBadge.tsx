import { X, Quote } from 'lucide-react';

interface Props {
  text: string;
  onDismiss: () => void;
}

export function TextSelectionBadge({ text, onDismiss }: Props) {
  const preview = text.length > 80 ? text.slice(0, 80) + '…' : text;

  return (
    <div className="mx-3 mb-2 flex items-start gap-2 bg-synkora-50/80 border border-synkora-100 rounded-2xl px-3 py-2.5 text-xs animate-fade-in shadow-soft">
      <Quote size={12} className="text-synkora-600 flex-shrink-0 mt-0.5" />
      <span className="text-brand-ink flex-1 italic leading-relaxed">{preview}</span>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 text-brand-muted/70 hover:text-brand-ink transition-colors"
        aria-label="Dismiss selection"
      >
        <X size={12} />
      </button>
    </div>
  );
}
