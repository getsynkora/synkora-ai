import type { Metadata } from 'next'
import { headers } from 'next/headers'
import { getSharedConversation } from '@/lib/api/conversations'
import { extractMindsetShareData } from '@/lib/share/mindsetShare'
import { SharedChatView } from './SharedChatView'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

interface Props {
  params: Promise<{ token: string }>
}

function buildMetadataDescription(data: any) {
  const mindsetShare = extractMindsetShareData(data)
  if (mindsetShare) return mindsetShare.shareCaption
  if (data?.agent?.description) return data.agent.description
  return 'A shared Synkora conversation.'
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params

  try {
    const headerStore = await headers()
    const host = headerStore.get('x-forwarded-host') || headerStore.get('host')
    const protocol = headerStore.get('x-forwarded-proto') || (host?.includes('localhost') ? 'http' : 'https')
    const data = await getSharedConversation(token)
    const mindsetShare = extractMindsetShareData(data)
    const title = mindsetShare
      ? `${mindsetShare.headline} | Synkora Mindset Snapshot`
      : `${data?.conversation?.name || 'Shared Conversation'} | Synkora`
    const description = buildMetadataDescription(data)
    const ogImage = `${API_URL}/api/v1/public/share/${encodeURIComponent(token)}/image`

    return {
      ...(host && { metadataBase: new URL(`${protocol}://${host}`) }),
      title,
      description,
      openGraph: {
        title,
        description,
        type: 'article',
        siteName: 'Synkora',
        images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
      },
      twitter: {
        card: 'summary_large_image',
        title,
        description,
        images: [ogImage],
      },
    }
  } catch {
    return {
      title: 'Shared Conversation | Synkora',
      description: 'A shared Synkora conversation.',
    }
  }
}

export default async function SharePage({ params }: Props) {
  const { token } = await params

  let data = null
  let error: 'not_found' | 'error' | null = null

  try {
    data = await getSharedConversation(token)
  } catch (e: any) {
    error = e?.message === 'not_found' ? 'not_found' : 'error'
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-sm px-6">
          <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-2">Link not available</h1>
          <p className="text-sm text-gray-500">
            This share link has expired, been revoked, or does not exist.
          </p>
        </div>
      </div>
    )
  }

  return <SharedChatView data={data} />
}
