import { BookOpen } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Blog – Synkora',
  description: 'Stories, guides, and updates from the Synkora team. Coming soon.',
}

export default function BlogPage() {
  return (
    <PublicPageFrame>
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#ffe8de] text-[#cf673e] mb-6">
          <BookOpen className="w-8 h-8" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-3">Blog coming soon</h1>
        <p className="text-gray-500 max-w-md text-base leading-relaxed">
          We&apos;re working on guides, product updates, and stories about building AI agents. Check back soon.
        </p>
      </div>
    </PublicPageFrame>
  )
}
