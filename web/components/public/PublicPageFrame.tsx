import type { ReactNode } from 'react'

import AnimatedNav from '@/components/landing/AnimatedNav'
import Footer from '@/components/landing/Footer'

export default function PublicPageFrame({
  children,
  mainClassName = 'pt-28',
}: {
  children: ReactNode
  mainClassName?: string
}) {
  return (
    <div className="public-page min-h-screen">
      <AnimatedNav />
      <main className={mainClassName}>{children}</main>
      <Footer />
    </div>
  )
}
