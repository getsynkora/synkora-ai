'use client'

import { useEffect, useState } from 'react'
export { formatStars } from '@/lib/utils/formatStars'

export function useGitHubStars(): number | null {
  const [stars, setStars] = useState<number | null>(null)

  useEffect(() => {
    fetch('/api/github-stars')
      .then((r) => r.json())
      .then((d) => setStars(d.stars ?? null))
      .catch(() => null)
  }, [])

  return stars
}
