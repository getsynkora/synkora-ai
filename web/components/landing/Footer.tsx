'use client'

import Link from 'next/link'
import { Zap } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="py-12 px-6 bg-gray-900 text-white">
      <div className="max-w-7xl mx-auto">
        {/* Main Content - Compact Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-10">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <Link href="/" className="flex items-center gap-2 mb-4">
              <div className="w-9 h-9 bg-red-500 rounded-lg flex items-center justify-center">
                <Zap className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold">Synkora</span>
            </Link>
            <p className="text-gray-400 text-sm leading-relaxed">
              The open-source LLM application platform. Build, deploy, and manage AI agents at any scale.
            </p>
          </div>

          {/* Product */}
          <div>
            <h4 className="font-semibold text-white mb-4 text-sm uppercase tracking-wider">Product</h4>
            <ul className="space-y-2.5">
              <li>
                <Link href="/how-it-works" className="text-gray-400 hover:text-white text-sm transition-colors">
                  How It Works
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Pricing
                </Link>
              </li>
              <li>
                <Link href="/use-cases" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Use Cases
                </Link>
              </li>
              <li>
                <Link href="/alternatives" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Alternatives
                </Link>
              </li>
              <li>
                <Link href="https://docs.synkora.ai" target="_blank" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Documentation
                </Link>
              </li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h4 className="font-semibold text-white mb-4 text-sm uppercase tracking-wider">Company</h4>
            <ul className="space-y-2.5">
              <li>
                <Link href="/about" className="text-gray-400 hover:text-white text-sm transition-colors">
                  About
                </Link>
              </li>
              <li>
                <Link href="/contact" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Contact
                </Link>
              </li>
              <li>
                <Link href="https://blog.synkora.ai" target="_blank" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Blog
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h4 className="font-semibold text-white mb-4 text-sm uppercase tracking-wider">Legal</h4>
            <ul className="space-y-2.5">
              <li>
                <Link href="/terms" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Terms
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Privacy
                </Link>
              </li>
              <li>
                <Link href="/security" className="text-gray-400 hover:text-white text-sm transition-colors">
                  Security
                </Link>
              </li>
            </ul>
          </div>

          {/* Connect */}
          <div>
            <h4 className="font-semibold text-white mb-4 text-sm uppercase tracking-wider">Connect</h4>
            <div className="flex items-center gap-3">
              {/* GitHub */}
              <Link
                href="https://github.com/getsynkora/synkora-ai"
                target="_blank"
                className="w-9 h-9 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors"
                aria-label="GitHub"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
              </Link>
              {/* Discord */}
              <Link
                href="https://discord.gg/synkora-ai"
                target="_blank"
                className="w-9 h-9 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors"
                aria-label="Discord"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z"/>
                </svg>
              </Link>
              {/* Twitter/X */}
              <Link
                href="https://twitter.com/synkora_ai"
                target="_blank"
                className="w-9 h-9 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors"
                aria-label="Twitter"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
              </Link>
              {/* LinkedIn */}
              <Link
                href="https://linkedin.com/company/synkora-ai"
                target="_blank"
                className="w-9 h-9 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors"
                aria-label="LinkedIn"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                </svg>
              </Link>
              {/* Facebook */}
              <Link
                href="https://facebook.com/synkora.ai"
                target="_blank"
                className="w-9 h-9 bg-gray-800 hover:bg-gray-700 rounded-lg flex items-center justify-center transition-colors"
                aria-label="Facebook"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                </svg>
              </Link>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-gray-800 pt-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-gray-400 text-sm">
              © {new Date().getFullYear()} Synkora. All rights reserved.
            </p>
            <div className="flex items-center gap-4">
              <span className="px-3 py-1 bg-gray-800 rounded-full text-xs text-gray-400 font-medium">
                MIT License
              </span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
