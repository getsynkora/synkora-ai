'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { ArrowLeft, Globe, Eye, Plus, Trash2, Save, Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface GalleryImage {
  url: string
  caption?: string
  order: number
}

interface ConvMessage {
  role: 'user' | 'assistant'
  content: string
}

interface ExampleConv {
  title: string
  messages: ConvMessage[]
}

interface ProfileData {
  slug?: string
  tagline?: string
  long_description?: string
  hero_image_url?: string
  preview_video_url?: string
  gallery_images?: GalleryImage[]
  example_conversations?: ExampleConv[]
  creator_bio?: string
  creator_display_name?: string
  seo_title?: string
  seo_description?: string
  og_image_url?: string
  cta_label?: string
  accent_color?: string
  is_published?: boolean
}

type Section = 'hero' | 'description' | 'gallery' | 'examples' | 'seo'

export default function LandingPageEditorPage() {
  const params = useParams()
  const router = useRouter()
  const agentName = params.agentName as string

  const [activeSection, setActiveSection] = useState<Section>('hero')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [profile, setProfile] = useState<ProfileData>({})
  const [slug, setSlug] = useState<string | null>(null)
  const [isPublished, setIsPublished] = useState(false)

  useEffect(() => {
    async function loadProfile() {
      try {
        const res = await apiClient.request('GET', `/api/v1/agents/${agentName}/public-profile`)
        if (res?.profile) {
          setProfile(res.profile)
          setSlug(res.profile.slug)
          setIsPublished(res.profile.is_published || false)
        }
      } catch {
        // No profile yet — that's fine
      } finally {
        setLoading(false)
      }
    }
    loadProfile()
  }, [agentName])

  const handleSave = async () => {
    setSaving(true)
    try {
      await apiClient.request('PUT', `/api/v1/agents/${agentName}/public-profile`, profile)
      toast.success('Landing page saved')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async () => {
    setPublishing(true)
    try {
      // Always save current state first so accent_color and other changes are persisted
      await apiClient.request('PUT', `/api/v1/agents/${agentName}/public-profile`, profile)
      const res = await apiClient.request('POST', `/api/v1/agents/${agentName}/public-profile/publish`)
      setIsPublished(true)
      setSlug(res?.slug)
      toast.success('Landing page published!')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Publish failed')
    } finally {
      setPublishing(false)
    }
  }

  const updateProfile = (updates: Partial<ProfileData>) => {
    setProfile(prev => ({ ...prev, ...updates }))
  }

  const addGalleryImage = () => {
    const images = profile.gallery_images || []
    updateProfile({ gallery_images: [...images, { url: '', caption: '', order: images.length }] })
  }

  const removeGalleryImage = (i: number) => {
    const images = (profile.gallery_images || []).filter((_, idx) => idx !== i)
    updateProfile({ gallery_images: images })
  }

  const addExample = () => {
    const examples = profile.example_conversations || []
    updateProfile({
      example_conversations: [
        ...examples,
        { title: 'Example conversation', messages: [{ role: 'user', content: '' }, { role: 'assistant', content: '' }] }
      ]
    })
  }

  const removeExample = (i: number) => {
    updateProfile({ example_conversations: (profile.example_conversations || []).filter((_, idx) => idx !== i) })
  }

  const sections: { id: Section; label: string }[] = [
    { id: 'hero', label: 'Hero' },
    { id: 'description', label: 'Description' },
    { id: 'gallery', label: 'Gallery' },
    { id: 'examples', label: 'Examples' },
    { id: 'seo', label: 'SEO' },
  ]

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-500" />
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between flex-wrap gap-4">
        <div>
          <Link
            href={`/agents/${agentName}/edit`}
            className="mb-2 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back to Edit
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Landing Page</h1>
          <p className="text-sm text-gray-500 mt-1">
            {isPublished && slug
              ? <span>Published at <a href={`/a/${slug}`} target="_blank" className="text-primary-600 hover:underline">/a/{slug}</a></span>
              : 'Not published yet'
            }
          </p>
        </div>
        <div className="flex gap-3">
          {isPublished && slug && (
            <a
              href={`/a/${slug}`}
              target="_blank"
              className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:border-gray-300"
            >
              <Eye className="h-4 w-4" />
              Preview
            </a>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save draft
          </button>
          <button
            onClick={handlePublish}
            disabled={publishing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
            {isPublished ? 'Republish' : 'Publish'}
          </button>
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex gap-1 mb-8 bg-gray-100 rounded-xl p-1">
        {sections.map(s => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
              activeSection === s.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Section content */}
      <div className="space-y-6">

        {/* Hero section */}
        {activeSection === 'hero' && (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-white p-6">
              <h2 className="font-semibold text-gray-900 mb-4">Hero</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Slug (URL path)</label>
                  <input
                    type="text"
                    value={profile.slug || ''}
                    onChange={e => updateProfile({ slug: e.target.value })}
                    placeholder="my-awesome-agent"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">Your page will be at /a/{profile.slug || 'your-slug'}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Tagline</label>
                  <input
                    type="text"
                    value={profile.tagline || ''}
                    onChange={e => updateProfile({ tagline: e.target.value })}
                    placeholder="One-line hook for your agent"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Hero Image URL</label>
                  <input
                    type="url"
                    value={profile.hero_image_url || ''}
                    onChange={e => updateProfile({ hero_image_url: e.target.value })}
                    placeholder="https://..."
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Preview Video URL</label>
                  <input
                    type="url"
                    value={profile.preview_video_url || ''}
                    onChange={e => updateProfile({ preview_video_url: e.target.value })}
                    placeholder="YouTube/Vimeo embed URL"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">CTA Button Label</label>
                    <input
                      type="text"
                      value={profile.cta_label || ''}
                      onChange={e => updateProfile({ cta_label: e.target.value })}
                      placeholder="Try it free"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Accent Color</label>
                    <input
                      type="color"
                      value={profile.accent_color || '#ff444f'}
                      onChange={e => updateProfile({ accent_color: e.target.value })}
                      className="w-full h-10 border border-gray-300 rounded-md px-1 py-1 cursor-pointer"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Creator Display Name</label>
                  <input
                    type="text"
                    value={profile.creator_display_name || ''}
                    onChange={e => updateProfile({ creator_display_name: e.target.value })}
                    placeholder="Your name"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Creator Bio</label>
                  <textarea
                    value={profile.creator_bio || ''}
                    onChange={e => updateProfile({ creator_bio: e.target.value })}
                    placeholder="Brief bio shown at the bottom of your landing page"
                    rows={2}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 resize-none"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Description section */}
        {activeSection === 'description' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Description</h2>
            <p className="text-xs text-gray-400 mb-2">Supports markdown formatting</p>
            <textarea
              value={profile.long_description || ''}
              onChange={e => updateProfile({ long_description: e.target.value })}
              placeholder="Describe your agent in detail. What does it do? Who is it for? What can users expect?"
              rows={12}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 resize-y font-mono"
            />
          </div>
        )}

        {/* Gallery section */}
        {activeSection === 'gallery' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Gallery Images</h2>
              <button
                onClick={addGalleryImage}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-primary-50 hover:bg-primary-100 text-primary-700 rounded-lg text-sm font-medium"
              >
                <Plus className="h-4 w-4" /> Add image
              </button>
            </div>
            <div className="space-y-3">
              {(profile.gallery_images || []).map((img, i) => (
                <div key={i} className="flex gap-3 items-start p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1 space-y-2">
                    <input
                      type="url"
                      value={img.url}
                      onChange={e => {
                        const imgs = [...(profile.gallery_images || [])]
                        imgs[i] = { ...imgs[i], url: e.target.value }
                        updateProfile({ gallery_images: imgs })
                      }}
                      placeholder="Image URL"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                    />
                    <input
                      type="text"
                      value={img.caption || ''}
                      onChange={e => {
                        const imgs = [...(profile.gallery_images || [])]
                        imgs[i] = { ...imgs[i], caption: e.target.value }
                        updateProfile({ gallery_images: imgs })
                      }}
                      placeholder="Caption (optional)"
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                    />
                  </div>
                  <button onClick={() => removeGalleryImage(i)} className="text-red-400 hover:text-red-600 mt-1">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {!(profile.gallery_images?.length) && (
                <p className="text-center py-8 text-gray-400 text-sm">No images yet. Add your first gallery image.</p>
              )}
            </div>
          </div>
        )}

        {/* Examples section */}
        {activeSection === 'examples' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Example Conversations</h2>
              <button
                onClick={addExample}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-primary-50 hover:bg-primary-100 text-primary-700 rounded-lg text-sm font-medium"
              >
                <Plus className="h-4 w-4" /> Add example
              </button>
            </div>
            <div className="space-y-4">
              {(profile.example_conversations || []).map((ex, i) => (
                <div key={i} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <input
                      type="text"
                      value={ex.title}
                      onChange={e => {
                        const exs = [...(profile.example_conversations || [])]
                        exs[i] = { ...exs[i], title: e.target.value }
                        updateProfile({ example_conversations: exs })
                      }}
                      placeholder="Conversation title"
                      className="flex-1 border-0 border-b border-gray-200 pb-1 text-sm font-medium focus:outline-none focus:border-emerald-500"
                    />
                    <button onClick={() => removeExample(i)} className="text-red-400 hover:text-red-600 ml-3">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  {ex.messages.map((msg, j) => (
                    <div key={j} className="flex gap-2 mb-2">
                      <select
                        value={msg.role}
                        onChange={e => {
                          const exs = [...(profile.example_conversations || [])]
                          exs[i].messages[j] = { ...exs[i].messages[j], role: e.target.value as 'user' | 'assistant' }
                          updateProfile({ example_conversations: exs })
                        }}
                        className="w-24 border border-gray-300 rounded px-2 py-1.5 text-xs"
                      >
                        <option value="user">User</option>
                        <option value="assistant">Assistant</option>
                      </select>
                      <input
                        type="text"
                        value={msg.content}
                        onChange={e => {
                          const exs = [...(profile.example_conversations || [])]
                          exs[i].messages[j] = { ...exs[i].messages[j], content: e.target.value }
                          updateProfile({ example_conversations: exs })
                        }}
                        placeholder="Message content"
                        className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm focus:border-primary-500 focus:outline-none"
                      />
                    </div>
                  ))}
                </div>
              ))}
              {!(profile.example_conversations?.length) && (
                <p className="text-center py-8 text-gray-400 text-sm">No examples yet.</p>
              )}
            </div>
          </div>
        )}

        {/* SEO section */}
        {activeSection === 'seo' && (
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h2 className="font-semibold text-gray-900 mb-4">SEO & Social</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Meta Title</label>
                <input
                  type="text"
                  value={profile.seo_title || ''}
                  onChange={e => updateProfile({ seo_title: e.target.value })}
                  placeholder="Page title for search engines"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Meta Description</label>
                <textarea
                  value={profile.seo_description || ''}
                  onChange={e => updateProfile({ seo_description: e.target.value })}
                  placeholder="Description for search engines (120-160 chars)"
                  rows={3}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">OG Image URL</label>
                <input
                  type="url"
                  value={profile.og_image_url || ''}
                  onChange={e => updateProfile({ og_image_url: e.target.value })}
                  placeholder="Image shown when shared on social media"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:border-primary-500 focus:outline-none"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
