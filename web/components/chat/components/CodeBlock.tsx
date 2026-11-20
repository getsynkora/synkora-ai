'use client'

import dynamic from 'next/dynamic'
import { Copy } from 'lucide-react'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

// Lazy-load the Prism parser (~480 KB with all grammars) — only downloaded when
// a code block appears in a message. The style JSON is tiny and imported normally.
const SyntaxHighlighter = dynamic(
  () => import('react-syntax-highlighter').then((m) => ({ default: m.Prism })),
  {
    ssr: false,
    loading: () => (
      <pre className="bg-ink text-sand p-4 text-[13px] font-mono overflow-x-auto whitespace-pre">{}</pre>
    ),
  }
)

interface CodeBlockProps {
  language?: string
  code: string
}

export function CodeBlock({ language, code }: CodeBlockProps) {
  return (
    <div className="not-prose relative group/code my-3 max-w-full overflow-hidden rounded-lg">
      <div className="flex items-center justify-between px-3 py-1.5 bg-ink rounded-t-lg border-b border-ink-soft">
        <span className="text-xs text-ash font-mono">{language || 'code'}</span>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-ash hover:text-white transition-colors flex items-center gap-1"
        >
          <Copy size={12} />
          Copy
        </button>
      </div>
      <div className="overflow-x-auto max-h-80 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(156,163,175,0.4) transparent' }}>
        <SyntaxHighlighter
          style={vscDarkPlus as never}
          language={language || 'text'}
          PreTag="div"
          className="!rounded-t-none !rounded-b-lg !my-0 !text-[13px]"
          customStyle={{ margin: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}
