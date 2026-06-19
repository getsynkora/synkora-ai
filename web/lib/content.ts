import 'server-only'

import fs from 'node:fs/promises'
import path from 'node:path'

const REPO_ROOT = path.join(process.cwd(), '..')
const DOCS_ROOT = path.join(REPO_ROOT, 'docs', 'docs')
const BLOG_ROOT = path.join(REPO_ROOT, 'docs', 'blog')
const AUTHORS_FILE = path.join(REPO_ROOT, 'docs', 'blog', 'authors.yml')

const SECTION_ORDER = [
  'overview',
  'getting-started',
  'concepts',
  'api-reference',
  'guides',
  'sdk',
  'architecture',
] as const

type FrontmatterValue = string | number | boolean | string[]

export interface AuthorProfile {
  key: string
  name: string
  title?: string
  url?: string
}

export interface BlogPostSummary {
  slug: string
  title: string
  excerpt: string
  publishedAt: string | null
  tags: string[]
  authors: AuthorProfile[]
}

export interface BlogPost extends BlogPostSummary {
  content: string
}

export interface DocSummary {
  slugParts: string[]
  href: string
  title: string
  description: string
  section: string
  subgroup: string | null
  order: number | null
  sourcePath: string
}

export interface DocPage extends DocSummary {
  content: string
}

export interface DocNavGroup {
  label: string
  items: Array<{ title: string; href: string }>
}

export interface DocNavSection {
  label: string
  items: Array<{ title: string; href: string }>
  groups: DocNavGroup[]
}

function normalizeLineEndings(value: string) {
  return value.replace(/\r\n/g, '\n')
}

function stripQuotes(value: string) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1)
  }
  return value
}

function parseFrontmatterValue(rawValue: string): FrontmatterValue {
  const value = rawValue.trim()

  if (value.startsWith('[') && value.endsWith(']')) {
    const inner = value.slice(1, -1).trim()
    if (!inner) return []
    return inner
      .split(',')
      .map((item) => stripQuotes(item.trim()))
      .filter(Boolean)
  }

  if (value === 'true') return true
  if (value === 'false') return false
  if (/^-?\d+$/.test(value)) return Number(value)

  return stripQuotes(value)
}

function parseFrontmatter(source: string): {
  data: Record<string, FrontmatterValue>
  content: string
} {
  const normalized = normalizeLineEndings(source)
  if (!normalized.startsWith('---\n')) {
    return { data: {}, content: normalized }
  }

  const endIndex = normalized.indexOf('\n---\n', 4)
  if (endIndex === -1) {
    return { data: {}, content: normalized }
  }

  const rawBlock = normalized.slice(4, endIndex)
  const content = normalized.slice(endIndex + 5)
  const data: Record<string, FrontmatterValue> = {}

  for (const line of rawBlock.split('\n')) {
    const separatorIndex = line.indexOf(':')
    if (separatorIndex === -1) continue
    const key = line.slice(0, separatorIndex).trim()
    const value = line.slice(separatorIndex + 1).trim()
    if (!key) continue
    data[key] = parseFrontmatterValue(value)
  }

  return { data, content }
}

function titleCase(value: string) {
  return value
    .split(/[-/]/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function stripMarkdown(value: string) {
  return value
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^>\s?/gm, '')
    .replace(/^#+\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function extractTitle(markdown: string) {
  const match = markdown.match(/^#\s+(.+)$/m)
  return match?.[1]?.trim() ?? 'Untitled'
}

function extractDescription(markdown: string) {
  const lines = markdown.split('\n')

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    if (trimmed.startsWith('#')) continue
    if (trimmed.startsWith(':::')) continue
    if (trimmed.startsWith('<')) continue

    const cleaned = stripMarkdown(trimmed)
    if (cleaned) return cleaned
  }

  return ''
}

function extractExcerpt(markdown: string) {
  const [beforeTruncate] = markdown.split('<!-- truncate -->')
  return extractDescription(beforeTruncate || markdown)
}

// These directives are handled by MarkdownContent.tsx — pass them through unchanged.
const EDITORIAL_DIRECTIVES = new Set(['eyebrow', 'centered-statement', 'brush-title', 'ink-band', 'pipeline'])

function transformAdmonitions(markdown: string) {
  const lines = markdown.split('\n')
  const output: string[] = []
  let inAdmonition = false
  let admonitionTitle = ''
  let inEditorial = false

  for (const line of lines) {
    // Check for editorial directives first — pass through as-is
    const editorialOpening = line.match(/^:::(eyebrow|centered-statement|brush-title|ink-band|pipeline)\s*$/)
    if (editorialOpening) {
      inEditorial = true
      output.push(line)
      continue
    }

    if (inEditorial && line.trim() === ':::') {
      inEditorial = false
      output.push(line)
      continue
    }

    if (inEditorial) {
      output.push(line)
      continue
    }

    // Standard admonition → blockquote conversion
    const opening = line.match(/^:::(\w+)(?:\s+(.*))?$/)
    if (opening && !EDITORIAL_DIRECTIVES.has(opening[1])) {
      inAdmonition = true
      const kind = opening[1].trim()
      admonitionTitle = opening[2]?.trim() || titleCase(kind)
      output.push(`> **${admonitionTitle}**`)
      continue
    }

    if (inAdmonition && line.trim() === ':::') {
      inAdmonition = false
      admonitionTitle = ''
      output.push('')
      continue
    }

    if (inAdmonition) {
      output.push(line ? `> ${line}` : '>')
      continue
    }

    output.push(line)
  }

  return output.join('\n')
}

function rewriteRelativeImageUrls(markdown: string, publicBasePath: string) {
  return markdown.replace(/!\[([^\]]*)\]\(((?:\.\/|\.\.\/)[^)]+)\)/g, (_match, altText: string, assetPath: string) => {
    const normalizedAssetPath = assetPath.replace(/\\/g, '/')
    const fileName = normalizedAssetPath.split('/').filter(Boolean).pop()
    if (!fileName) return `![${altText}](${assetPath})`
    return `![${altText}](${publicBasePath}/${fileName})`
  })
}

function transformMarkdown(markdown: string, options?: { relativeImageBasePath?: string }) {
  const withRewrittenImages = options?.relativeImageBasePath
    ? rewriteRelativeImageUrls(markdown, options.relativeImageBasePath)
    : markdown

  return transformAdmonitions(withRewrittenImages)
    .replace(/<!--\s*truncate\s*-->/g, '')
    .trim()
}

async function walkMarkdownFiles(root: string): Promise<string[]> {
  const entries = await fs.readdir(root, { withFileTypes: true })
  const files = await Promise.all(
    entries.map(async (entry) => {
      const absolutePath = path.join(root, entry.name)
      if (entry.isDirectory()) {
        return walkMarkdownFiles(absolutePath)
      }

      if (!entry.isFile()) return []
      if (!entry.name.endsWith('.md') && !entry.name.endsWith('.mdx')) return []
      return [absolutePath]
    })
  )

  return files.flat().sort()
}

async function readFile(absolutePath: string) {
  return fs.readFile(absolutePath, 'utf8')
}

async function loadAuthors() {
  const raw = normalizeLineEndings(await readFile(AUTHORS_FILE))
  const authors: Record<string, AuthorProfile> = {}
  let currentKey: string | null = null

  for (const line of raw.split('\n')) {
    if (!line.trim()) continue
    const topLevel = line.match(/^([A-Za-z0-9_-]+):\s*$/)
    if (topLevel) {
      currentKey = topLevel[1]
      authors[currentKey] = {
        key: currentKey,
        name: titleCase(currentKey),
      }
      continue
    }

    if (!currentKey) continue
    const field = line.match(/^\s+([A-Za-z0-9_]+):\s*(.+)\s*$/)
    if (!field) continue

    const [, key, rawValue] = field
    const value = stripQuotes(rawValue.trim())

    if (key === 'name') authors[currentKey].name = value
    if (key === 'title') authors[currentKey].title = value
    if (key === 'url') authors[currentKey].url = value
  }

  return authors
}

function getSectionOrder(section: string) {
  const index = SECTION_ORDER.indexOf(section as (typeof SECTION_ORDER)[number])
  return index === -1 ? SECTION_ORDER.length : index
}

function sortDocs(a: DocSummary, b: DocSummary) {
  const sectionOrderDiff = getSectionOrder(a.section) - getSectionOrder(b.section)
  if (sectionOrderDiff !== 0) return sectionOrderDiff

  const subgroupA = a.subgroup ?? ''
  const subgroupB = b.subgroup ?? ''
  const subgroupDiff = subgroupA.localeCompare(subgroupB)
  if (subgroupDiff !== 0) return subgroupDiff

  const orderA = a.order ?? Number.MAX_SAFE_INTEGER
  const orderB = b.order ?? Number.MAX_SAFE_INTEGER
  if (orderA !== orderB) return orderA - orderB

  return a.title.localeCompare(b.title)
}

export async function getAllBlogPosts(): Promise<BlogPost[]> {
  const [files, authorsByKey] = await Promise.all([
    walkMarkdownFiles(BLOG_ROOT),
    loadAuthors(),
  ])

  const posts = await Promise.all(
    files.map(async (absolutePath) => {
      const fileName = path.basename(absolutePath)
      const raw = await readFile(absolutePath)
      const { data, content } = parseFrontmatter(raw)

      const slug =
        typeof data.slug === 'string'
          ? data.slug
          : fileName.replace(/\.(md|mdx)$/i, '').replace(/^\d{4}-\d{2}-\d{2}-/, '')

      const authors =
        Array.isArray(data.authors) && data.authors.length > 0
          ? data.authors
              .map((authorKey) => authorsByKey[authorKey] || { key: authorKey, name: titleCase(authorKey) })
          : [authorsByKey.synkora || { key: 'synkora', name: 'Synkora Team' }]

      const tags = Array.isArray(data.tags) ? data.tags : []
      const publishedAtMatch = fileName.match(/^(\d{4}-\d{2}-\d{2})-/)

      return {
        slug,
        title: typeof data.title === 'string' ? data.title : extractTitle(content),
        excerpt: extractExcerpt(content),
        publishedAt: publishedAtMatch?.[1] ?? null,
        tags,
        authors,
        content: transformMarkdown(content, { relativeImageBasePath: '/images/blog' }),
      } satisfies BlogPost
    })
  )

  return posts.sort((a, b) => (a.publishedAt && b.publishedAt ? b.publishedAt.localeCompare(a.publishedAt) : 0))
}

export async function getBlogPostBySlug(slug: string): Promise<BlogPost | null> {
  const posts = await getAllBlogPosts()
  return posts.find((post) => post.slug === slug) ?? null
}

export async function getAllDocs(): Promise<DocPage[]> {
  const files = await walkMarkdownFiles(DOCS_ROOT)

  const docs = await Promise.all(
    files.map(async (absolutePath) => {
      const raw = await readFile(absolutePath)
      const { data, content } = parseFrontmatter(raw)
      const relativePath = path.relative(DOCS_ROOT, absolutePath)
      const withoutExtension = relativePath.replace(/\.(md|mdx)$/i, '')
      const parts = withoutExtension.split(path.sep)
      const isIntro = parts.length === 1 && parts[0] === 'intro'
      const slugFromFrontmatter =
        typeof data.slug === 'string' && data.slug !== '/' ? data.slug.replace(/^\/+|\/+$/g, '') : null
      const slugParts = isIntro
        ? []
        : slugFromFrontmatter
          ? slugFromFrontmatter.split('/').filter(Boolean)
          : parts

      const title = extractTitle(content)
      const section = isIntro ? 'overview' : slugParts[0] || 'overview'
      const subgroup = slugParts.length > 2 ? slugParts[1] : slugParts.length === 2 ? null : null
      const href = isIntro ? '/docs' : `/docs/${slugParts.join('/')}`

      return {
        slugParts,
        href,
        title,
        description: extractDescription(content),
        section,
        subgroup,
        order: typeof data.sidebar_position === 'number' ? data.sidebar_position : null,
        sourcePath: relativePath,
        content: transformMarkdown(content),
      } satisfies DocPage
    })
  )

  return docs.sort(sortDocs)
}

export async function getDocsNavigation(): Promise<DocNavSection[]> {
  const docs = await getAllDocs()
  const sections = new Map<string, DocNavSection>()

  for (const doc of docs) {
    if (doc.slugParts.length === 0) continue

    const sectionKey = doc.section
    const sectionLabel = titleCase(sectionKey)
    const existing = sections.get(sectionKey) ?? {
      label: sectionLabel,
      items: [],
      groups: [],
    }

    if (doc.slugParts.length === 1) {
      existing.items.push({ title: doc.title, href: doc.href })
    } else {
      const groupLabel = titleCase(doc.slugParts[1])
      let group = existing.groups.find((item) => item.label === groupLabel)
      if (!group) {
        group = { label: groupLabel, items: [] }
        existing.groups.push(group)
      }
      group.items.push({ title: doc.title, href: doc.href })
    }

    sections.set(sectionKey, existing)
  }

  return [
    {
      label: 'Overview',
      items: [{ title: 'Welcome', href: '/docs' }],
      groups: [],
    },
    ...Array.from(sections.entries())
      .sort(([a], [b]) => getSectionOrder(a) - getSectionOrder(b))
      .map(([, section]) => section),
  ]
}

export async function getDocBySlug(slugParts: string[]): Promise<DocPage | null> {
  const docs = await getAllDocs()
  return docs.find((doc) => doc.slugParts.join('/') === slugParts.join('/')) ?? null
}

export async function getDocsHomeSections() {
  const docs = await getAllDocs()
  const grouped = new Map<
    string,
    {
      label: string
      description: string
      href: string
      count: number
    }
  >()

  for (const doc of docs) {
    if (doc.slugParts.length === 0) continue
    const key = doc.section
    const entry = grouped.get(key) ?? {
      label: titleCase(key),
      description: doc.description,
      href: doc.href,
      count: 0,
    }
    entry.count += 1
    if (!entry.description && doc.description) {
      entry.description = doc.description
    }
    grouped.set(key, entry)
  }

  return Array.from(grouped.entries())
    .sort(([a], [b]) => getSectionOrder(a) - getSectionOrder(b))
    .map(([, value]) => value)
}

export async function getAdjacentDocs(slugParts: string[]) {
  const docs = await getAllDocs()
  const docsWithOverview = [
    {
      slugParts: [] as string[],
      href: '/docs',
      title: 'Welcome',
      description: 'Overview of Synkora documentation',
      section: 'overview',
      subgroup: null,
      order: 0,
      sourcePath: 'intro.md',
    },
    ...docs.filter((doc) => doc.slugParts.length > 0),
  ]

  const currentIndex = docsWithOverview.findIndex((doc) => doc.slugParts.join('/') === slugParts.join('/'))
  if (currentIndex === -1) {
    return { previous: null, next: null }
  }

  return {
    previous: currentIndex > 0 ? docsWithOverview[currentIndex - 1] : null,
    next: currentIndex < docsWithOverview.length - 1 ? docsWithOverview[currentIndex + 1] : null,
  }
}
