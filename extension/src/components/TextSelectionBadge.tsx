import { X, Quote } from 'lucide-react';

interface Props {
  text: string;
  onDismiss: () => void;
}

export function TextSelectionBadge({ text, onDismiss }: Props) {
  const preview = text.length > 80 ? text.slice(0, 80) + '…' : text;

  return (
    <div className="mx-3 mb-2 flex items-start gap-2 bg-synkora-50 border border-synkora-100 rounded-lg px-3 py-2 text-xs animate-fade-in">
      <Quote size={12} className="text-synkora-500 flex-shrink-0 mt-0.5" />
      <span className="text-synkora-700 flex-1 italic leading-relaxed">{preview}</span>
      <button
        onClick={onDismiss}
        className="flex-shrink-0 text-synkora-400 hover:text-synkora-600 transition-colors"
        aria-label="Dismiss selection"
      >
        <X size={12} />
      </button>
    </div>
  );
}
