'use client'

import { useEffect } from 'react'

/** Keeps <html lang> in step with the language shown (the root layout cannot know it). */
export function HtmlLang({ locale }: { locale: string }) {
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])
  return null
}
