import Link from 'next/link'
import { Zap, Users, Target, Sparkles, Code, Globe, Heart, ArrowRight } from 'lucide-react'

export const metadata = {
  title: 'About – Synkora',
  description: 'Synkora is an open-source, multitenant LLM application platform for building, deploying, and managing AI agents with API-first architecture and enterprise-grade tenant isolation.',
}

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-pink-50">
      {/* Navigation */}
      <nav className="py-4 px-4 sm:px-6 border-b border-gray-100 bg-white/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-9 h-9 bg-red-500 rounded-lg flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Synkora</span>
          </Link>
          <Link
            href="/signin"
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >
            Sign In
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-12 sm:py-20 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-full text-sm font-semibold mb-6">
            <Heart className="w-4 h-4" />
            About Us
          </div>
          <h1 className="text-3xl sm:text-5xl font-bold text-gray-900 mb-6">
            The Open-Source
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-red-600 to-rose-600">
              LLM Application Platform
            </span>
          </h1>
          <p className="text-base sm:text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            Synkora is an open-source, multitenant platform that lets you build, deploy, and manage AI agents and LLM-powered applications — with API-first architecture, multi-provider model routing, and enterprise-grade tenant isolation.
          </p>
        </div>
      </section>

      {/* Mission Section */}
      <section className="py-12 sm:py-16 px-4 sm:px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl font-bold text-gray-900 mb-6">Our Mission</h2>
              <p className="text-lg text-gray-600 mb-6 leading-relaxed">
                Every startup struggles with the same problem: too much work, too few hands. Hiring is expensive and slow. We believe AI can change that — not by replacing humans, but by giving every team the infrastructure to build AI-powered teammates that handle the repetitive, time-consuming parts of work.
              </p>
              <p className="text-lg text-gray-600 leading-relaxed">
                Synkora gives you the platform to build AI agents for product management, engineering, marketing, support, and more — all on one open-source, API-first foundation with your own LLM keys and full tenant isolation.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gradient-to-br from-red-50 to-pink-50 rounded-2xl p-6 border border-red-100">
                <Target className="w-10 h-10 text-red-500 mb-4" />
                <h3 className="font-bold text-gray-900 mb-2">API-First Architecture</h3>
                <p className="text-sm text-gray-600">REST, SSE, and WebSocket for chat, workflows, and agent invocation</p>
              </div>
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-6 border border-blue-100">
                <Code className="w-10 h-10 text-blue-500 mb-4" />
                <h3 className="font-bold text-gray-900 mb-2">Multitenant by Design</h3>
                <p className="text-sm text-gray-600">Per-tenant isolation, API keys, quotas, and model configs</p>
              </div>
              <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-6 border border-green-100">
                <Globe className="w-10 h-10 text-green-500 mb-4" />
                <h3 className="font-bold text-gray-900 mb-2">Open Source</h3>
                <p className="text-sm text-gray-600">MIT licensed, transparent, community-driven development</p>
              </div>
              <div className="bg-gradient-to-br from-purple-50 to-violet-50 rounded-2xl p-6 border border-purple-100">
                <Sparkles className="w-10 h-10 text-purple-500 mb-4" />
                <h3 className="font-bold text-gray-900 mb-2">LLM-Native</h3>
                <p className="text-sm text-gray-600">Model routing, prompt caching, cost optimization, and observability</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* What We Do Section */}
      <section className="py-12 sm:py-16 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 mb-12 text-center">AI Teammates for Every Role</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
              <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center mb-6 text-2xl">
                <span>PM</span>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">AI Product Manager</h3>
              <p className="text-gray-600 leading-relaxed">
                Backlog prioritization, sprint planning, status reports. Integrates with Jira, Linear, Notion, and Slack to keep your projects on track.
              </p>
            </div>
            <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center mb-6 text-2xl">
                <span>ENG</span>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">AI Software Engineer</h3>
              <p className="text-gray-600 leading-relaxed">
                Code review, bug triage, documentation generation. Integrates with GitHub, GitLab, Sentry, and CI/CD pipelines.
              </p>
            </div>
            <div className="bg-white rounded-2xl p-8 shadow-sm border border-gray-100">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center mb-6 text-2xl">
                <span>MKT</span>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-3">AI Marketing Lead</h3>
              <p className="text-gray-600 leading-relaxed">
                Content creation, SEO optimization, campaign analysis. Integrates with HubSpot, Analytics, and social media platforms.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Team Section */}
      <section className="py-12 sm:py-16 px-4 sm:px-6 bg-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-6">Built by Raju Mazumder</h2>
          <p className="text-lg text-gray-600 mb-8 leading-relaxed">
            Synkora was created by <strong>Raju Mazumder</strong>, a passionate software engineer with
            extensive experience in building enterprise-grade applications. With a vision to make
            AI accessible to everyone, Raju designed Synkora as a comprehensive platform that
            combines the power of modern AI with production-ready infrastructure.
          </p>
          <p className="text-lg text-gray-600 mb-6 leading-relaxed">
            The project is open-source and welcomes contributions from developers around the world.
            Whether you're interested in AI, distributed systems, or building great developer tools,
            there's a place for you in the Synkora community.
          </p>
          <a
            href="https://linkedin.com/in/rajumazumder"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
            </svg>
            Connect on LinkedIn
          </a>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-12 sm:py-16 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-gradient-to-br from-red-600 via-red-500 to-rose-600 rounded-3xl p-12 text-center shadow-xl">
            <h2 className="text-3xl font-bold text-white mb-4">Ready to Build Your AI Team?</h2>
            <p className="text-lg text-white/90 mb-8 max-w-xl mx-auto">
              Start with a template or build from scratch. Deploy your first AI agent in minutes.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-8 py-4 bg-white hover:bg-gray-50 text-red-600 font-semibold rounded-xl transition-all shadow-lg"
              >
                <Zap className="w-5 h-5" />
                Get Started Free
              </Link>
              <Link
                href="https://github.com/rajuniit/synkora-ai"
                target="_blank"
                className="inline-flex items-center gap-2 px-8 py-4 bg-white/10 hover:bg-white/20 text-white font-semibold rounded-xl transition-all border border-white/20"
              >
                View on GitHub
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-gray-200 bg-white">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-gray-500 text-sm">
            © {new Date().getFullYear()} Synkora. All rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <Link href="/terms" className="text-gray-500 hover:text-gray-700 text-sm">Terms</Link>
            <Link href="/privacy" className="text-gray-500 hover:text-gray-700 text-sm">Privacy</Link>
            <Link href="/security" className="text-gray-500 hover:text-gray-700 text-sm">Security</Link>
            <Link href="/contact" className="text-gray-500 hover:text-gray-700 text-sm">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
