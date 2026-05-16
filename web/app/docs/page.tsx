import { FileText } from 'lucide-react'
import PublicPageFrame from '@/components/public/PublicPageFrame'

export const metadata = {
  title: 'Docs – Synkora',
  description: 'Documentation for the Synkora platform. Coming soon.',
}

export default function DocsPage() {
  return (
    <PublicPageFrame>
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#e4f2ef] text-[#2d8b69] mb-6">
          <FileText className="w-8 h-8" />
        </div>
        <h1 className="text-3xl font-bold text-gray-900 mb-3">Docs coming soon</h1>
        <p className="text-gray-500 max-w-md text-base leading-relaxed">
          Full API reference, integration guides, and tutorials are on the way. In the meantime, reach us at{' '}
          <a href="mailto:support@synkora.ai" className="text-[#2d8b69] hover:underline">
            support@synkora.ai
          </a>
          .
        </p>
      </div>
    </PublicPageFrame>
  )
}
