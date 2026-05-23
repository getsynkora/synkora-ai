type ShareMessage = {
  role?: string | null
  content?: string | null
  metadata?: Record<string, any> | null
}

type ShareConversationPayload = {
  conversation?: { name?: string | null } | null
  agent?: { name?: string | null; description?: string | null } | null
  messages?: ShareMessage[] | null
}

export interface MindsetShareData {
  classification: string
  tone: 'growth' | 'mixed' | 'fixed'
  headline: string
  shareCaption: string
  insight: string
  domain: string
  scorePercent: number | null
  scoreLabel: string | null
  strengths: string[]
  growthEdges: string[]
}

const CLASSIFICATION_RULES = [
  { tone: 'growth', label: 'Growth mindset', pattern: /\bgrowth mindset\b/i },
  { tone: 'mixed', label: 'Mixed mindset', pattern: /\bmixed mindset\b/i },
  { tone: 'fixed', label: 'Fixed mindset', pattern: /\bfixed mindset\b/i },
] as const

const DOMAIN_RULES = [
  { label: 'Coding', pattern: /\b(code|coding|developer|engineering|programming|software)\b/i },
  { label: 'Leadership', pattern: /\b(leader|leadership|manager|management|team lead)\b/i },
  { label: 'Learning', pattern: /\b(learning|study|student|studying|education)\b/i },
  { label: 'Career', pattern: /\b(career|work|job|profession|promotion)\b/i },
  { label: 'Fitness', pattern: /\b(fitness|gym|training|exercise|workout)\b/i },
  { label: 'Relationships', pattern: /\b(relationship|dating|marriage|partner|family)\b/i },
] as const

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function normalizeWhitespace(value: string): string {
  return value.replace(/\r/g, '').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
}

function stripMarkdown(value: string): string {
  return value
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`(.*?)`/g, '$1')
    .replace(/^#+\s+/gm, '')
    .trim()
}

function toSentenceCase(value: string): string {
  if (!value) return value
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function cleanLine(value: string): string {
  return stripMarkdown(value)
    .replace(/^[-*•]\s+/, '')
    .replace(/^\d+\.\s+/, '')
    .replace(/^["']|["']$/g, '')
    .trim()
}

function simplifySignalText(value: string): string {
  let cleaned = cleanLine(value).replace(/^[^a-zA-Z0-9]+/, '').trim()
  const dashed = cleaned.split(/\s+[—-]\s+/)
  if (dashed.length > 1) cleaned = dashed.slice(1).join(' - ').trim()
  cleaned = cleaned.replace(/\bThis is the most significant [^.]+\./i, '').trim()
  const sentenceMatch = cleaned.match(/^(.{0,180}?[.!?])(?:\s|$)/)
  return (sentenceMatch?.[1] || cleaned).trim()
}

function ensureSentence(value: string): string {
  return /[.!?]$/.test(value) ? value : `${value}.`
}

function getToneFromClassification(classification: string): MindsetShareData['tone'] {
  const normalized = classification.toLowerCase()
  if (normalized.includes('growth')) return 'growth'
  if (normalized.includes('fixed')) return 'fixed'
  return 'mixed'
}

function normalizeClassification(value?: unknown): string | null {
  if (typeof value !== 'string') return null
  const trimmed = stripMarkdown(value).trim()
  for (const rule of CLASSIFICATION_RULES) {
    if (rule.pattern.test(trimmed)) return rule.label
  }
  return null
}

function extractClassification(content: string): string | null {
  for (const rule of CLASSIFICATION_RULES) {
    if (rule.pattern.test(content)) return rule.label
  }

  const resultLabel = extractLabeledValue(content, /(classification|result|mindset type)/i)
  return normalizeClassification(resultLabel)
}

function normalizeScorePercent(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (value <= 1) return clamp(Math.round(value * 100), 0, 100)
    return clamp(Math.round(value), 0, 100)
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return null

    const fraction = trimmed.match(/^([01](?:\.\d+)?)$/)
    if (fraction) return clamp(Math.round(Number.parseFloat(fraction[1]) * 100), 0, 100)

    const percent = trimmed.match(/^(\d{1,3})(?:\s*%|\s*\/\s*100)?$/)
    if (percent) return clamp(Number.parseInt(percent[1], 10), 0, 100)
  }

  return null
}

function extractScorePercent(content: string): number | null {
  const labeledPercent = content.match(
    /(?:score|mindset score|growth score|overall score)[^\d]{0,12}(\d{1,3})(?:\s*%|\s*\/\s*100)/i
  )
  if (labeledPercent) return clamp(Number.parseInt(labeledPercent[1], 10), 0, 100)

  const labeledFraction = content.match(
    /(?:score|mindset score|growth score|overall score)[^\d]{0,12}([01](?:\.\d+)?)/i
  )
  if (labeledFraction) return clamp(Math.round(Number.parseFloat(labeledFraction[1]) * 100), 0, 100)

  return null
}

function formatScoreLabel(scorePercent: number | null): string | null {
  if (scorePercent == null) return null
  return `${scorePercent}/100 growth orientation`
}

function extractLabeledValue(content: string, labelPattern: RegExp): string | null {
  const lines = normalizeWhitespace(content).split('\n')
  for (const line of lines) {
    const cleaned = cleanLine(line)
    if (!cleaned) continue
    const match = cleaned.match(new RegExp(`^${labelPattern.source}\\s*[:\\-]\\s*(.+)$`, labelPattern.flags))
    if (match?.[1]) return match[1].trim()
  }

  const inline = content.match(new RegExp(`${labelPattern.source}\\s*[:\\-]\\s*([^\\n]+)`, labelPattern.flags))
  return inline?.[1]?.trim() || null
}

function extractSectionItems(content: string, headingPattern: RegExp): string[] {
  const blocks = normalizeWhitespace(content).split('\n')
  const items: string[] = []
  let inSection = false

  for (const rawLine of blocks) {
    const line = rawLine.trim()
    const cleaned = cleanLine(line)

    if (!cleaned) {
      if (inSection && items.length > 0) break
      continue
    }

    if (headingPattern.test(cleaned)) {
      inSection = true
      continue
    }

    if (
      inSection &&
      /^(headline|share caption|classification|result|score|insight|summary|next step|strengths?|growth edges?|top fixed signals?|top growth signals?)/i.test(cleaned)
    ) {
      break
    }

    if (!inSection) continue

    if (/^[-*•]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      items.push(simplifySignalText(line))
      continue
    }

    if (items.length === 0) items.push(simplifySignalText(cleaned))
  }

  return items.slice(0, 3)
}

function extractHeadline(content: string, classification: string, domain: string): string {
  const labeledHeadline = extractLabeledValue(content, /headline/i)
  if (labeledHeadline) return stripMarkdown(labeledHeadline)

  const tone = getToneFromClassification(classification)
  if (tone === 'growth') return `Growth is already your default in ${domain.toLowerCase()}.`
  if (tone === 'fixed') return `Your current default in ${domain.toLowerCase()} is protection before progress.`
  return `You are closer to growth than you think in ${domain.toLowerCase()}.`
}

function inferDomain(payload: ShareConversationPayload, messages: ShareMessage[]): string {
  const samples = [
    payload.conversation?.name || '',
    payload.agent?.name || '',
    payload.agent?.description || '',
    ...messages.map(message => `${message.role || ''} ${message.content || ''}`),
  ]

  const combined = samples.join('\n')
  for (const rule of DOMAIN_RULES) {
    if (rule.pattern.test(combined)) return rule.label
  }

  return 'Mindset'
}

function fallbackInsight(classification: string, domain: string): string {
  const tone = getToneFromClassification(classification)
  if (tone === 'growth') {
    return `You already treat challenge in ${domain.toLowerCase()} as something you can build through practice, feedback, and repetition.`
  }
  if (tone === 'fixed') {
    return `Under pressure in ${domain.toLowerCase()}, your default is self-protection. The opportunity is learning to read struggle as signal, not identity.`
  }
  return `You already believe growth is possible in ${domain.toLowerCase()}, but pressure can still pull you back toward comfort, certainty, or self-protection.`
}

function buildShareCaption(data: {
  classification: string
  domain: string
  scoreLabel: string | null
  strengths: string[]
  growthEdges: string[]
}): string {
  const strength = data.strengths[0]
  const edge = data.growthEdges[0]
  const scorePart = data.scoreLabel ? ` ${data.scoreLabel}.` : ''
  const base = `I ran a Synkora mindset assessment on my ${data.domain.toLowerCase()} style. Result: ${data.classification}.${scorePart}`

  const tone = getToneFromClassification(data.classification)
  if (tone === 'growth') {
    return [
      base,
      strength ? `Strongest signal: ${ensureSentence(toSentenceCase(strength))}` : 'My strongest signal was choosing stretch over certainty.',
      edge ? `Next unlock: ${ensureSentence(toSentenceCase(edge))}` : 'Next unlock: make that response consistent under pressure.',
    ].join(' ')
  }

  if (tone === 'fixed') {
    return [
      base,
      edge ? `Biggest blocker: ${ensureSentence(toSentenceCase(edge))}` : 'Biggest blocker: defaulting to self-protection when things get hard.',
      'Clear signal on what to improve next.',
    ].join(' ')
  }

  return [
    base,
    strength ? `The good news: ${ensureSentence(toSentenceCase(strength))}` : 'The good news: growth is already present.',
    edge ? `The work now is ${ensureSentence(edge)}` : 'The work now is staying growth-oriented when the stakes feel higher.',
  ].join(' ')
}

function extractInsight(content: string, classification: string, domain: string): string {
  const labeledInsight = extractLabeledValue(content, /(insight|summary|core insight|one-line insight)/i)
  if (labeledInsight) return stripMarkdown(labeledInsight)
  return fallbackInsight(classification, domain)
}

function normalizeItems(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map(item => (typeof item === 'string' ? simplifySignalText(item) : ''))
    .filter(Boolean)
    .slice(0, 3)
}

function extractFromMetadata(message: ShareMessage, payload: ShareConversationPayload): MindsetShareData | null {
  const result = message.metadata?.mindset_result
  if (!result || typeof result !== 'object') return null

  const classification = normalizeClassification(result.classification) || extractClassification(message.content || '')
  if (!classification) return null

  const domain = typeof result.domain === 'string' && result.domain.trim()
    ? stripMarkdown(result.domain)
    : inferDomain(payload, payload.messages || [])

  const scorePercent =
    normalizeScorePercent(result.score_percent) ??
    normalizeScorePercent(result.score) ??
    extractScorePercent(message.content || '')

  const strengths = [
    ...normalizeItems(result.strengths),
    ...normalizeItems(result.top_growth_signals),
  ].slice(0, 3)

  const growthEdges = [
    ...normalizeItems(result.growth_edges),
    ...normalizeItems(result.top_fixed_signals),
  ].slice(0, 3)

  const headline =
    (typeof result.headline === 'string' && stripMarkdown(result.headline)) ||
    extractHeadline(message.content || '', classification, domain)

  const shareCaption =
    (typeof result.share_caption === 'string' && stripMarkdown(result.share_caption)) ||
    buildShareCaption({
      classification,
      domain,
      scoreLabel: formatScoreLabel(scorePercent),
      strengths,
      growthEdges,
    })

  const insight =
    (typeof result.insight === 'string' && stripMarkdown(result.insight)) ||
    extractInsight(message.content || '', classification, domain)

  return {
    classification,
    tone: getToneFromClassification(classification),
    headline,
    shareCaption,
    insight,
    domain,
    scorePercent,
    scoreLabel: formatScoreLabel(scorePercent),
    strengths,
    growthEdges,
  }
}

function extractFromContent(message: ShareMessage, payload: ShareConversationPayload): MindsetShareData | null {
  const content = normalizeWhitespace(message.content || '')
  if (!content) return null

  const classification = extractClassification(content)
  if (!classification) return null

  const domain = inferDomain(payload, payload.messages || [])
  const scorePercent = extractScorePercent(content)
  const strengths = extractSectionItems(
    content,
    /^[^a-zA-Z0-9]*(strengths?|top growth signals?|growth signals?|strongest growth-pattern signals?|what(?:'| i)?s working)/i
  )
  const growthEdges = extractSectionItems(
    content,
    /^[^a-zA-Z0-9]*(growth edges?|top fixed signals?|fixed signals?|strongest fixed-pattern signals?|watchouts?|what to work on|next steps?)/i
  )
  const headline = extractHeadline(content, classification, domain)
  const insight = extractInsight(content, classification, domain)
  const shareCaption =
    extractLabeledValue(content, /share caption|share-ready caption|post copy/i) ||
    buildShareCaption({
      classification,
      domain,
      scoreLabel: formatScoreLabel(scorePercent),
      strengths,
      growthEdges,
    })

  return {
    classification,
    tone: getToneFromClassification(classification),
    headline,
    shareCaption,
    insight,
    domain,
    scorePercent,
    scoreLabel: formatScoreLabel(scorePercent),
    strengths,
    growthEdges,
  }
}

export function extractMindsetShareData(payload: ShareConversationPayload): MindsetShareData | null {
  const messages = (payload.messages || []).filter(message => (message.role || '').toLowerCase() === 'assistant')

  for (const message of [...messages].reverse()) {
    const fromMetadata = extractFromMetadata(message, payload)
    if (fromMetadata) return fromMetadata

    const fromContent = extractFromContent(message, payload)
    if (fromContent) return fromContent
  }

  return null
}

export function buildSocialShareText(data: MindsetShareData, url?: string): string {
  const base = `${data.headline} ${data.shareCaption}`.trim()
  return url ? `${base} ${url}` : base
}

export function buildLinkedInShareUrl(url: string): string {
  return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`
}

export function buildXShareUrl(url: string, text: string): string {
  return `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`
}
