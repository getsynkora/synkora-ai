import { ImageResponse } from 'next/og'
import { getSharedConversation } from '@/lib/api/conversations'
import { extractMindsetShareData } from '@/lib/share/mindsetShare'

export const runtime = 'nodejs'
export const size = {
  width: 1200,
  height: 630,
}
export const contentType = 'image/png'

function truncate(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength - 1).trim()}…`
}

function normalizeLine(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function getPalette(tone: 'growth' | 'mixed' | 'fixed' | undefined) {
  if (tone === 'growth') {
    return {
      primary: '#06B6D4',
      secondary: '#3B82F6',
      text: '#CFFAFE',
      soft: 'rgba(6,182,212,0.18)',
    }
  }

  if (tone === 'fixed') {
    return {
      primary: '#8B5CF6',
      secondary: '#7C3AED',
      text: '#E9D5FF',
      soft: 'rgba(139,92,246,0.20)',
    }
  }

  return {
    primary: '#7C3AED',
    secondary: '#3B82F6',
    text: '#DDD6FE',
    soft: 'rgba(124,58,237,0.20)',
  }
}

export default async function OpenGraphImage({
  params,
}: {
  params: Promise<{ token: string }>
}) {
  const { token } = await params

  let headline = 'You are closer to growth than you think.'
  let classification = 'Mixed mindset'
  let domain = 'Coding'
  let insight = 'Pressure can still pull you back toward comfort, certainty, or self-protection.'
  let strength = 'Belief that practice, feedback, and persistence can improve capability.'
  let nextEdge = 'Recover with a better strategy after setbacks.'
  let scorePercent: number | null = 44
  let tone: 'growth' | 'mixed' | 'fixed' | undefined = 'mixed'

  try {
    const data = await getSharedConversation(token)
    const share = extractMindsetShareData(data)

    if (share) {
      headline = truncate(normalizeLine(share.headline), 56)
      classification = share.classification
      domain = share.domain
      insight = truncate(normalizeLine(share.insight || insight), 102)
      strength = truncate(normalizeLine(share.strengths[0] || strength), 56)
      nextEdge = truncate(normalizeLine(share.growthEdges[0] || nextEdge), 56)
      scorePercent = share.scorePercent ?? scorePercent
      tone = share.tone
    } else {
      headline = truncate(normalizeLine(data.conversation?.name || headline), 56)
    }
  } catch {
    // Fallback content remains usable.
  }

  const palette = getPalette(tone)
  const score = scorePercent == null ? 0 : Math.max(0, Math.min(100, scorePercent))
  const scoreText = scorePercent == null ? '--' : `${scorePercent}`

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          position: 'relative',
          overflow: 'hidden',
          fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
          color: '#FFFFFF',
          background:
            'linear-gradient(135deg, #070B16 0%, #0C1222 48%, #0F1730 100%)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(circle at 12% 16%, rgba(124,58,237,0.22), transparent 24%), radial-gradient(circle at 88% 10%, rgba(59,130,246,0.18), transparent 20%)',
          }}
        />

        <div
          style={{
            position: 'absolute',
            inset: 34,
            display: 'flex',
            borderRadius: 34,
            border: '1px solid rgba(255,255,255,0.08)',
            background: 'rgba(16,22,40,0.90)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
          }}
        >
          <div
            style={{
              width: 316,
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '28px 28px 24px 28px',
              background: `linear-gradient(180deg, ${palette.primary} 0%, ${palette.secondary} 100%)`,
              borderTopLeftRadius: 34,
              borderBottomLeftRadius: 34,
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 12,
                    background: 'rgba(7,11,22,0.16)',
                    border: '1px solid rgba(255,255,255,0.18)',
                    fontSize: 20,
                    fontWeight: 800,
                  }}
                >
                  S
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <div style={{ fontSize: 18, fontWeight: 700 }}>Synkora</div>
                  <div style={{ fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.78)' }}>
                    Mindset Scorecard
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, marginTop: 18 }}>
                <div
                  style={{
                    fontSize: 144,
                    lineHeight: 0.9,
                    fontWeight: 800,
                    letterSpacing: '-0.08em',
                  }}
                >
                  {scoreText}
                </div>
                <div
                  style={{
                    fontSize: 28,
                    lineHeight: 1.1,
                    fontWeight: 700,
                    color: 'rgba(255,255,255,0.82)',
                    marginBottom: 24,
                  }}
                >
                  /100
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{classification}</div>
                <div style={{ fontSize: 12, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.82)' }}>
                  {domain}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div
                style={{
                  width: '100%',
                  height: 14,
                  display: 'flex',
                  borderRadius: 999,
                  background: 'rgba(7,11,22,0.18)',
                  border: '1px solid rgba(255,255,255,0.16)',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${score}%`,
                    height: '100%',
                    display: 'flex',
                    borderRadius: 999,
                    background: 'rgba(255,255,255,0.92)',
                  }}
                />
              </div>

              <div style={{ fontSize: 14, color: 'rgba(255,255,255,0.86)' }}>
                Growth score {score}%
              </div>

              <div style={{ fontSize: 17, lineHeight: 1.35, color: '#FFFFFF' }}>
                Interesting enough to post.
                <br />
                Clear enough to understand.
              </div>
            </div>
          </div>

          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              padding: '34px 34px 22px 34px',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    borderRadius: 999,
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    padding: '8px 14px',
                    fontSize: 12,
                    letterSpacing: '0.16em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.50)',
                  }}
                >
                  Mindset Result
                </div>

                <div
                  style={{
                    fontSize: 12,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.40)',
                  }}
                >
                  Synkora AI
                </div>
              </div>

              <div
                style={{
                  maxWidth: 680,
                  fontSize: 82,
                  lineHeight: 0.94,
                  fontWeight: 800,
                  letterSpacing: '-0.08em',
                }}
              >
                {headline}
              </div>

              <div
                style={{
                  maxWidth: 660,
                  fontSize: 25,
                  lineHeight: 1.28,
                  color: 'rgba(255,255,255,0.76)',
                }}
              >
                {insight}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', gap: 16 }}>
                <div
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    padding: '18px 20px',
                    borderRadius: 24,
                    background: 'rgba(255,255,255,0.04)',
                    border: `1px solid ${palette.soft}`,
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      letterSpacing: '0.16em',
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.42)',
                    }}
                  >
                    Strongest Signal
                  </div>
                  <div
                    style={{
                      fontSize: 22,
                      lineHeight: 1.25,
                      color: 'rgba(255,255,255,0.94)',
                    }}
                  >
                    {strength}
                  </div>
                </div>

                <div
                  style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10,
                    padding: '18px 20px',
                    borderRadius: 24,
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.10)',
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      letterSpacing: '0.16em',
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.42)',
                    }}
                  >
                    Next Growth Edge
                  </div>
                  <div
                    style={{
                      fontSize: 22,
                      lineHeight: 1.25,
                      color: 'rgba(255,255,255,0.94)',
                    }}
                  >
                    {nextEdge}
                  </div>
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    letterSpacing: '0.18em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.30)',
                  }}
                >
                  Social Scorecard Export
                </div>

                <div
                  style={{
                    fontSize: 12,
                    letterSpacing: '0.12em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.34)',
                  }}
                >
                  Synkora AI
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
    size
  )
}
