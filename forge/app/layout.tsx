import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Synkora Forge - AI Engineering Interview Arena',
  description:
    'A separate Synkora product vertical for Big Tech AI engineering interview practice, system design, coding, group prep, and upskilling.',
  openGraph: {
    title: 'Synkora Forge - AI Engineering Interview Arena',
    description:
      'Practice coding, system design, AI engineering, and group mock loops in a story-driven arena powered by Synkora.',
    type: 'website',
    siteName: 'Synkora Forge',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
