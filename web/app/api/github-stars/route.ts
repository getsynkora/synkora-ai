import { NextResponse } from 'next/server'

export const revalidate = 3600

export async function GET() {
  try {
    const res = await fetch('https://api.github.com/repos/getsynkora/synkora-ai', {
      headers: { Accept: 'application/vnd.github+json' },
      next: { revalidate: 3600 },
    })
    if (!res.ok) return NextResponse.json({ stars: null })
    const data = await res.json()
    return NextResponse.json({ stars: data.stargazers_count ?? null })
  } catch {
    return NextResponse.json({ stars: null })
  }
}
