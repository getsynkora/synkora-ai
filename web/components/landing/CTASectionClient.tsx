import Link from 'next/link'
import Footer from '@/components/landing/Footer'
import { formatStars } from '@/lib/utils/formatStars'

export default function CTASectionClient({ stars }: { stars?: number | null }) {
  return (
    <>
      <section className="landing bg-paper px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-4xl text-center">
          <div className="rounded-2xl bg-ink p-12 md:p-16">
            <h2 className="mb-5 text-4xl font-medium tracking-[-0.05em] text-white md:text-5xl">
              Own your AI infrastructure
            </h2>
            <p className="mx-auto mb-8 max-w-xl text-lg text-white/80 md:text-xl">
              Enterprise SSO, RBAC, audit logs, and full self-hosting, on your infrastructure and under your control. MIT licensed with no usage fees.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="https://app.synkora.ai/signup"
                className="inline-flex items-center rounded-full bg-mint px-8 py-4 font-semibold text-ink transition-colors hover:bg-white"
              >
                Get Started Free
              </Link>
              <a
                href="mailto:enterprise@synkora.ai"
                className="inline-flex items-center rounded-full border border-white/25 px-8 py-4 font-semibold text-white transition-colors hover:bg-white/10"
              >
                Talk to Sales
              </a>
              <a
                href="https://github.com/getsynkora/synkora-ai"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-full px-6 py-4 font-semibold text-white/70 transition-colors hover:text-white"
              >
                <svg aria-hidden="true" className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                  </svg>
                {stars != null ? formatStars(stars) : 'GitHub'}
              </a>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  )
}
