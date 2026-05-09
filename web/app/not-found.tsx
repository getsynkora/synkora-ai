import Link from 'next/link'
import { Zap, ArrowRight, Home, BookOpen, DollarSign } from 'lucide-react'

export const metadata = {
  title: 'Page Not Found – Synkora',
  description: 'The page you are looking for does not exist.',
}

export default function NotFound() {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      <nav className="border-b border-gray-100 px-6 py-4">
        <Link href="/" className="flex items-center gap-2 w-fit">
          <div className="w-9 h-9 bg-red-500 rounded-lg flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold text-gray-900">Synkora</span>
        </Link>
      </nav>

      <div className="flex-1 flex items-center justify-center px-6 py-20">
        <div className="text-center max-w-lg">
          <div className="text-8xl font-black text-gray-100 mb-4 select-none">404</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-3">Page not found</h1>
          <p className="text-gray-500 mb-10">
            The page you are looking for does not exist or has been moved.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-12">
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-xl transition-colors"
            >
              <Home className="w-4 h-4" />
              Back to Home
            </Link>
            <Link
              href="https://app.synkora.ai/signup"
              className="inline-flex items-center gap-2 px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-xl transition-colors"
            >
              Get Started Free
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-3 gap-4 text-sm">
            <Link href="/how-it-works" className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-100 hover:border-red-200 hover:bg-red-50 transition-colors group">
              <BookOpen className="w-5 h-5 text-gray-400 group-hover:text-red-500" />
              <span className="text-gray-600 group-hover:text-red-600 font-medium">How It Works</span>
            </Link>
            <Link href="/pricing" className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-100 hover:border-red-200 hover:bg-red-50 transition-colors group">
              <DollarSign className="w-5 h-5 text-gray-400 group-hover:text-red-500" />
              <span className="text-gray-600 group-hover:text-red-600 font-medium">Pricing</span>
            </Link>
            <Link href="/alternatives" className="flex flex-col items-center gap-2 p-4 rounded-xl border border-gray-100 hover:border-red-200 hover:bg-red-50 transition-colors group">
              <Zap className="w-5 h-5 text-gray-400 group-hover:text-red-500" />
              <span className="text-gray-600 group-hover:text-red-600 font-medium">Alternatives</span>
            </Link>
          </div>
        </div>
      </div>

      <footer className="border-t border-gray-100 px-6 py-6 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} Synkora. MIT License.
      </footer>
    </div>
  )
}
