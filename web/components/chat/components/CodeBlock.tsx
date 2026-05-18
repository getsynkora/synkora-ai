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
      <pre className="bg-gray-900 text-gray-100 p-4 text-[13px] font-mono overflow-x-auto whitespace-pre">{}</pre>
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
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 rounded-t-lg border-b border-gray-700">
        <span className="text-xs text-gray-400 font-mono">{language || 'code'}</span>
        <button
          onClick={() => navigator.clipboard.writeText(code)}
          className="text-xs text-gray-400 hover:text-white transition-colors flex items-center gap-1"
        >
          <Copy size={12} />
          Copy
        </button>
      </div>
      <div className="overflow-x-auto">
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
