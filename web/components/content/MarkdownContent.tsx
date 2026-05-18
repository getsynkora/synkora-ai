import Link from 'next/link'
import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function MarkdownContent({ content }: { content: string }) {
  const blocks = parseEditorialBlocks(content)

  return (
    <div className="content-markdown">
      {blocks.map((block, index) => {
        if (block.type === 'markdown') {
          return <MarkdownBlock key={index} content={block.content} />
        }

        if (block.type === 'eyebrow') {
          return (
            <div key={index} className="content-eyebrow">
              {block.content}
            </div>
          )
        }

        if (block.type === 'centered-statement') {
          return (
            <div key={index} className="content-centered-statement">
              {block.content.split('\n').filter(Boolean).map((line, lineIndex) => (
                <div key={lineIndex}>{line}</div>
              ))}
            </div>
          )
        }

        if (block.type === 'brush-title') {
          const lines = block.content.split('\n').filter(Boolean)
          return (
            <div key={index} className="content-brush-title">
              {lines[0] ? <div className="content-brush-title__highlight">{lines[0]}</div> : null}
              {lines.slice(1).map((line, lineIndex) => (
                <div key={lineIndex} className="content-brush-title__line">
                  {line}
                </div>
              ))}
            </div>
          )
        }

        if (block.type === 'ink-band') {
          return (
            <div key={index} className="content-ink-band">
              <InlineMarkdown content={block.content} />
            </div>
          )
        }

        return null
      })}
    </div>
  )
}

function MarkdownBlock({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {content}
    </ReactMarkdown>
  )
}

function InlineMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: markdownComponents.a,
        strong: markdownComponents.strong,
        em: markdownComponents.em,
        p: ({ children }) => <>{children}</>,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

const markdownComponents = {
  a: ({ href, children }: { href?: string; children?: ReactNode }) => {
    if (!href) return <span>{children}</span>

    const isInternal = href.startsWith('/')
    if (isInternal) {
      return (
        <Link href={href} className="font-medium text-[#2d8b69] underline decoration-[#2d8b69]/30 underline-offset-4 hover:text-[#1f6d52]">
          {children}
        </Link>
      )
    }

    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-[#2d8b69] underline decoration-[#2d8b69]/30 underline-offset-4 hover:text-[#1f6d52]"
      >
        {children}
      </a>
    )
  },
  pre: ({ children }: { children?: ReactNode }) => (
    <pre className="overflow-x-auto rounded-2xl border border-black/10 bg-[#161412] p-4 text-[13px] leading-6 text-[#f5f0e8]">
      {children}
    </pre>
  ),
  code: ({
    className,
    children,
    ...props
  }: {
    className?: string
    children?: ReactNode
  }) => {
    const isInline = !className
    if (isInline) {
      return (
        <code
          {...props}
          className="rounded-md bg-black/[0.06] px-1.5 py-0.5 text-[0.95em] text-[#1f1d19]"
        >
          {children}
        </code>
      )
    }

    return (
      <code {...props} className={className}>
        {children}
      </code>
    )
  },
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="content-strong">{children}</strong>
  ),
  em: ({ children }: { children?: ReactNode }) => (
    <em className="content-emphasis">{children}</em>
  ),
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="rounded-r-2xl border-l-4 border-[#79dfbc] bg-[#ebf7f2] px-5 py-4 text-[#2b3a34]">
      {children}
    </blockquote>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="overflow-x-auto">
      <table>{children}</table>
    </div>
  ),
  img: ({ src, alt }: { src?: string | Blob; alt?: string }) => {
    if (!src || typeof src !== 'string') return null
    return (
      <figure className="content-figure">
        <img src={src} alt={alt || ''} />
        {alt ? <figcaption>{alt}</figcaption> : null}
      </figure>
    )
  },
} as const

type EditorialBlock =
  | { type: 'markdown'; content: string }
  | { type: 'eyebrow'; content: string }
  | { type: 'centered-statement'; content: string }
  | { type: 'brush-title'; content: string }
  | { type: 'ink-band'; content: string }

function parseEditorialBlocks(content: string): EditorialBlock[] {
  const lines = content.split('\n')
  const blocks: EditorialBlock[] = []
  let markdownBuffer: string[] = []

  const flushMarkdown = () => {
    const value = markdownBuffer.join('\n').trim()
    if (value) {
      blocks.push({ type: 'markdown', content: value })
    }
    markdownBuffer = []
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]
    const directive = line.match(/^:::(eyebrow|centered-statement|brush-title|ink-band)\s*$/)
    if (!directive) {
      markdownBuffer.push(line)
      continue
    }

    flushMarkdown()

    const type = directive[1] as EditorialBlock['type']
    const directiveLines: string[] = []
    i += 1

    while (i < lines.length && lines[i].trim() !== ':::') {
      directiveLines.push(lines[i])
      i += 1
    }

    blocks.push({
      type,
      content: directiveLines.join('\n').trim(),
    } as EditorialBlock)
  }

  flushMarkdown()
  return blocks
}
