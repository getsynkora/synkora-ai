import type { ReactNode } from 'react'
import Link from 'next/link'

export default function AuthPageFrame({
  children,
}: {
  children: ReactNode
}) {
  return (
    <div className="auth-page min-h-screen">
      <div className="mx-auto max-w-[1480px] px-6 py-6 lg:px-10">
        <div className="mb-8 flex items-center justify-between">
          <Link href="/" className="inline-flex flex-col">
            <div className="flex items-center gap-3">
              <span className="whitespace-nowrap text-[2rem] font-semibold leading-none tracking-[0.18em] text-[#141414]">
                SYNKORA
              </span>
              <span className="rounded-full border border-black/10 bg-white/65 px-2.5 py-1 text-[10px] font-semibold uppercase leading-none tracking-[0.24em] text-[#5d564c]">
                Beta
              </span>
            </div>
            <span className="mt-2 whitespace-nowrap text-xs uppercase tracking-[0.22em] text-[#7a7267]">
              Open-source AI platform
            </span>
          </Link>
          <div className="hidden items-center gap-4 sm:flex">
            <Link href="/signin" className="text-sm font-medium text-[#4e473e] transition-colors hover:text-black">
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded-[1.75rem] bg-[#181818] px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-[#f7f2e7] transition-transform hover:-translate-y-0.5"
            >
              Get Started
            </Link>
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}
