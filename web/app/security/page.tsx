import Link from 'next/link'
import { ShieldCheck, Lock, Key, Eye, Server, CheckCircle, AlertTriangle, Mail, UserCheck, Users, FileSearch, Fingerprint, KeyRound } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Security – Synkora Enterprise AI Platform',
  description: 'Enterprise security built in: SAML/OIDC SSO, RBAC, tamper-evident audit logs, IP allowlist, MultiFernet key rotation, MFA enforcement, and RS256/ES256 JWT. Self-host for full control.',
}

const enterpriseFeatures = [
  { icon: UserCheck, accent: '#79dfbc', title: 'SAML & OIDC SSO', description: 'One-click SSO with Okta, Azure AD, Google Workspace, and any SAML 2.0 or OIDC-compliant identity provider. JIT user provisioning included.' },
  { icon: Users, accent: '#79dfbc', title: 'RBAC & Custom Roles', description: 'Owner, Admin, Editor, Normal roles with granular per-resource permission overrides per tenant member via JSON custom_permissions.' },
  { icon: FileSearch, accent: '#79dfbc', title: 'Tamper-Evident Audit Logs', description: 'Chain-hashed audit trail of every action, SHA-256 chained entries. Export to CSV or JSON with X-Audit-Chain-Valid integrity header.' },
  { icon: Fingerprint, accent: '#79dfbc', title: 'MFA Enforcement', description: 'TOTP-based two-factor authentication with tenant-wide admin enforcement. Hashed SHA-256 backup recovery codes, consumed on use.' },
  { icon: Server, accent: '#f0c56d', title: 'IP Allowlisting', description: 'Restrict console access to specific IP addresses or CIDR ranges per tenant. Block unauthorized network access at the middleware layer.' },
  { icon: KeyRound, accent: '#f0c56d', title: 'Encryption Key Rotation', description: 'MultiFernet key rotation across 28 encrypted fields in 18 models. Dry-run preview mode, zero-downtime rotation, Celery-based async execution.' },
  { icon: Key, accent: '#f0c56d', title: 'RS256 / ES256 JWT', description: 'Asymmetric JWT signing with JWKS endpoint for public key distribution. Supports RS256, RS384, RS512, ES256. Token blacklist + version tracking.' },
  { icon: Lock, accent: '#f0c56d', title: 'Encryption at Rest', description: 'All API keys, OAuth tokens, secrets, and credentials encrypted with Fernet symmetric encryption. Sensitive fields excluded from all API responses.' },
  { icon: Eye, accent: '#79dfbc', title: 'XSS & Input Sanitization', description: '60+ pattern detection covering HTML5 attack vectors, script injection, and data URIs. Fail-closed design with comprehensive CSRF protection.' },
  { icon: ShieldCheck, accent: '#79dfbc', title: 'Secret Scanning', description: 'Automatic detection of leaked API keys and credentials in agent inputs. 13 regex patterns covering AWS, GitHub, Stripe, Twilio, and more.' },
  { icon: Server, accent: '#f0c56d', title: 'Rate Limiting', description: 'Redis-backed distributed rate limiting with per-endpoint configuration, trusted proxy support, and sliding window algorithms.' },
  { icon: CheckCircle, accent: '#f0c56d', title: 'Security Headers', description: 'CSP with nonces, HSTS with preload, X-Frame-Options DENY, Permissions-Policy, and pure ASGI middleware avoiding BaseHTTPMiddleware race conditions.' },
]

export default function SecurityPage() {
  return (
    <PublicPageFrame mainClassName="">
      {/* Hero */}
      <section className="relative overflow-hidden bg-paper px-4 pb-14 pt-28 sm:px-6 sm:pb-20 sm:pt-32">
        <div className="relative mx-auto max-w-4xl text-center">
          <h1 className="mb-6 text-4xl font-medium tracking-[-0.05em] text-ink sm:text-6xl">
            Security built in,
            <br />
            <span className="text-leaf">not bolted on</span>
          </h1>
          <p className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-ink-soft sm:text-xl">
            Every enterprise security control your team needs, SAML SSO, RBAC, audit logs, IP allowlisting, key rotation, and MFA enforcement, available out of the box.
          </p>
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <a
              href="mailto:security@synkora.ai"
              className="inline-flex items-center gap-2 rounded-full bg-ink px-7 py-3.5 font-semibold text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
            >
              <Mail className="h-4 w-4" />
              Report a vulnerability
            </a>
            <Link
              href="/docs/security"
              className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/65 px-7 py-3.5 font-semibold text-ink transition-colors hover:bg-white"
            >
              Security docs
            </Link>
          </div>
        </div>
      </section>

      {/* Enterprise security features grid */}
      <section className="bg-sand px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <div className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-medium tracking-[-0.05em] text-ink sm:text-4xl">Enterprise security features</h2>
            <p className="mx-auto max-w-2xl text-lg leading-relaxed text-ink-soft">
              Production-ready controls for teams that can't compromise on security or compliance.
            </p>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {enterpriseFeatures.map((f, idx) => (
              <div key={idx} className="rounded-[1.75rem] border border-black/10 bg-white/60 p-6 shadow-soft">
                <div
                  className="mb-4 flex h-11 w-11 items-center justify-center rounded-[1rem] border border-black/8"
                  style={{ background: `linear-gradient(135deg, ${f.accent}30, rgba(255,255,255,0.9))` }}
                >
                  <f.icon className="h-5 w-5 text-ink" />
                </div>
                <h3 className="mb-2 text-base font-semibold tracking-[-0.03em] text-ink">{f.title}</h3>
                <p className="text-sm leading-relaxed text-ink-soft">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Responsible disclosure */}
      <section className="bg-paper px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-[2rem] border border-black/10 bg-white/60 p-8 shadow-soft sm:p-10">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1rem] bg-honey/25">
                <AlertTriangle className="h-6 w-6 text-warn" />
              </div>
              <div>
                <h2 className="text-xl font-semibold tracking-[-0.03em] text-ink">Responsible Disclosure</h2>
                <p className="text-sm text-ink-mute">Do NOT create a public GitHub issue for security vulnerabilities</p>
              </div>
            </div>
            <div className="grid gap-8 md:grid-cols-2">
              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink-soft">Please include</h3>
                <ul className="space-y-2">
                  {['Description of the vulnerability', 'Steps to reproduce the issue', 'Potential impact assessment', 'Affected versions (if known)', 'Suggested fix (if any)'].map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-ink-soft">
                      <span className="mt-0.5 shrink-0 text-leaf">✓</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-semibold text-ink-soft">What to expect</h3>
                <ul className="space-y-2">
                  {['Acknowledgment within 48 hours', 'Regular progress updates', 'Credit in release notes (if desired)', 'Coordinated disclosure timeline', 'No legal action for good-faith research'].map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-ink-soft">
                      <span className="mt-0.5 shrink-0 text-leaf">✓</span>
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-8 border-t border-black/8 pt-6">
              <a
                href="mailto:security@synkora.ai"
                className="inline-flex items-center gap-2 rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper transition-transform motion-reduce:transition-none hover:-translate-y-0.5"
              >
                <Mail className="h-4 w-4" />
                security@synkora.ai
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Best practices */}
      <section className="bg-sand px-4 py-14 sm:px-6 sm:py-20">
        <div className="mx-auto max-w-4xl">
          <div className="mb-10 text-center">
            <h2 className="mb-3 text-3xl font-medium tracking-[-0.05em] text-ink">Security best practices</h2>
            <p className="text-ink-soft">Recommended configuration for production enterprise deployments</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              'Enable SAML or OIDC SSO and disable local password login for all staff',
              'Enforce MFA at the tenant level for all team members',
              'Configure IP allowlist to restrict console access to corporate networks',
              'Use RS256 or ES256 asymmetric JWT signing in production',
              'Rotate encryption keys quarterly using the key rotation task',
              'Review audit logs weekly and export for your SIEM',
              'Follow principle of least privilege, assign minimum required roles',
              'Use environment variables for all secrets, never commit API keys',
              'Configure rate limiting appropriate to your traffic patterns',
              'Enable HTTPS with HSTS preload on all production domains',
            ].map((practice, idx) => (
              <div key={idx} className="flex items-start gap-3 rounded-[1.25rem] border border-ink/10 bg-white p-4 text-sm text-ink-soft">
                <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-leaf" />
                {practice}
              </div>
            ))}
          </div>
        </div>
      </section>
    </PublicPageFrame>
  )
}
