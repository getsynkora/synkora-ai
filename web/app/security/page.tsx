import Link from 'next/link'
import { Zap, Shield, Lock, Key, Eye, Server, CheckCircle, AlertTriangle, Mail } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Security – Synkora',
  description: 'Synkora security practices: encryption, multi-tenancy isolation, vulnerability disclosure, and self-hosting for full infrastructure control.',
}

export default function SecurityPage() {
  return (
    <PublicPageFrame mainClassName="pt-28">
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-green-100 text-green-700 rounded-full text-sm font-semibold mb-6">
            <Shield className="w-4 h-4" />
            Security First
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
            Security at Synkora
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            We take security seriously. Learn about our security practices, how to report vulnerabilities,
            and our commitment to protecting your data.
          </p>
        </div>
      </section>

      {/* Report Vulnerability Section */}
      <section className="py-12 px-6 bg-white border-y border-gray-100">
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-2xl p-8 border border-amber-200">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-6 h-6 text-amber-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900 mb-2">Report a Security Vulnerability</h2>
                <p className="text-gray-600 mb-4">
                  If you've discovered a security vulnerability in Synkora, please report it responsibly.
                  <strong className="text-gray-900"> Do NOT create a public GitHub issue.</strong>
                </p>
                <a
                  href="mailto:security@synkora.ai"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-xl transition-colors"
                >
                  <Mail className="w-4 h-4" />
                  security@synkora.ai
                </a>
                <p className="text-sm text-gray-500 mt-3">
                  We acknowledge reports within 48 hours and provide regular updates on progress.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Security Features Section */}
      <section className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 mb-12 text-center">Security Features</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: Lock,
                title: 'Encryption at Rest',
                description: 'All sensitive data including API keys, OAuth tokens, and secrets are encrypted using Fernet symmetric encryption.',
                color: 'red',
              },
              {
                icon: Key,
                title: 'JWT Authentication',
                description: 'Secure token-based authentication with token blacklisting, version tracking, and automatic refresh.',
                color: 'blue',
              },
              {
                icon: Shield,
                title: 'CSRF Protection',
                description: 'Server-side CSRF token validation with Redis session binding and fail-closed design.',
                color: 'green',
              },
              {
                icon: Eye,
                title: 'Input Sanitization',
                description: 'Comprehensive XSS protection with 60+ pattern detection covering modern HTML5 attack vectors.',
                color: 'purple',
              },
              {
                icon: Server,
                title: 'Rate Limiting',
                description: 'Redis-backed distributed rate limiting with per-endpoint configuration and trusted proxy support.',
                color: 'orange',
              },
              {
                icon: CheckCircle,
                title: 'Security Headers',
                description: 'Content Security Policy with nonces, HSTS with preload, X-Frame-Options DENY, and Permissions-Policy.',
                color: 'teal',
              },
            ].map((feature, idx) => (
              <div key={idx} className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 ${
                  feature.color === 'red' ? 'bg-red-100' :
                  feature.color === 'blue' ? 'bg-blue-100' :
                  feature.color === 'green' ? 'bg-green-100' :
                  feature.color === 'purple' ? 'bg-purple-100' :
                  feature.color === 'orange' ? 'bg-orange-100' : 'bg-teal-100'
                }`}>
                  <feature.icon className={`w-6 h-6 ${
                    feature.color === 'red' ? 'text-red-600' :
                    feature.color === 'blue' ? 'text-blue-600' :
                    feature.color === 'green' ? 'text-green-600' :
                    feature.color === 'purple' ? 'text-purple-600' :
                    feature.color === 'orange' ? 'text-orange-600' : 'text-teal-600'
                  }`} />
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">{feature.title}</h3>
                <p className="text-gray-600 text-sm leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Security Practices Section */}
      <section className="py-16 px-6 bg-white">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 mb-8 text-center">Security Best Practices</h2>
          <div className="prose prose-lg max-w-none">
            <div className="bg-gray-50 rounded-2xl p-8">
              <h3 className="text-xl font-bold text-gray-900 mb-4">When Using Synkora</h3>
              <ul className="space-y-3">
                {[
                  'Keep dependencies updated to the latest secure versions',
                  'Use environment variables for all secrets and API keys',
                  'Enable authentication for all production deployments',
                  'Use HTTPS in production environments',
                  'Regularly review access logs and audit trails',
                  'Follow the principle of least privilege for team members',
                  'Configure rate limiting appropriate to your use case',
                  'Use secure session management with sessionStorage',
                  'Enable multi-factor authentication when available',
                  'Regularly rotate API keys and access tokens',
                ].map((practice, idx) => (
                  <li key={idx} className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700">{practice}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* What to Include Section */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">When Reporting a Vulnerability</h2>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl p-6 border border-gray-100">
              <h3 className="font-bold text-gray-900 mb-4">Please Include</h3>
              <ul className="space-y-2 text-gray-600">
                <li className="flex items-start gap-2">
                  <span className="text-green-500">•</span>
                  Description of the vulnerability
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500">•</span>
                  Steps to reproduce the issue
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500">•</span>
                  Potential impact assessment
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500">•</span>
                  Affected versions (if known)
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-500">•</span>
                  Suggested fix (if any)
                </li>
              </ul>
            </div>
            <div className="bg-white rounded-2xl p-6 border border-gray-100">
              <h3 className="font-bold text-gray-900 mb-4">What to Expect</h3>
              <ul className="space-y-2 text-gray-600">
                <li className="flex items-start gap-2">
                  <span className="text-blue-500">•</span>
                  Acknowledgment within 48 hours
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500">•</span>
                  Regular updates on progress
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500">•</span>
                  Credit in release notes (if desired)
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500">•</span>
                  Coordinated disclosure timeline
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500">•</span>
                  No legal action for good-faith research
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Supported Versions */}
      <section className="py-16 px-6 bg-white">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">Supported Versions</h2>
          <div className="bg-gray-50 rounded-2xl overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Version</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr>
                  <td className="px-6 py-4 text-gray-900 font-medium">Latest Release</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                      <CheckCircle className="w-4 h-4" />
                      Supported
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 text-gray-900 font-medium">Previous Releases</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-medium">
                      Not Supported
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-sm text-gray-500 text-center mt-4">
            We recommend always using the latest version for the best security and features.
          </p>
        </div>
      </section>

    </PublicPageFrame>
  )
}
