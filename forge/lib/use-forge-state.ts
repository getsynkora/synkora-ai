'use client'

import { useEffect, useState } from 'react'
import { defaultProfile, type ForgeProfile, type Scorecard } from '@/lib/forge-system'

const PROFILE_KEY = 'synkora-forge-profile'
const SCORECARDS_KEY = 'synkora-forge-scorecards'

export function useForgeProfile() {
  const [profile, setProfileState] = useState<ForgeProfile>(defaultProfile)

  useEffect(() => {
    const raw = window.localStorage.getItem(PROFILE_KEY)
    if (raw) setProfileState(JSON.parse(raw) as ForgeProfile)
  }, [])

  const setProfile = (next: ForgeProfile) => {
    setProfileState(next)
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(next))
  }

  return { profile, setProfile }
}

export function useForgeScorecards() {
  const [scorecards, setScorecards] = useState<Scorecard[]>([])

  useEffect(() => {
    const raw = window.localStorage.getItem(SCORECARDS_KEY)
    if (raw) setScorecards(JSON.parse(raw) as Scorecard[])
  }, [])

  const addScorecard = (scorecard: Scorecard) => {
    const next = [scorecard, ...scorecards].slice(0, 12)
    setScorecards(next)
    window.localStorage.setItem(SCORECARDS_KEY, JSON.stringify(next))
  }

  return { scorecards, addScorecard }
}
