'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import toast from 'react-hot-toast'
import { Globe, Eye, Plus, Trash2, Save, Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api/client'
import AgentPageShell, { AgentPagePanel, AgentPageTabs } from '@/components/agents/AgentPageShell'

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

  const fieldClass =
    'w-full rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-4 py-3 text-sm text-gray-900 placeholder-gray-400 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]'
  const textAreaClass = `${fieldClass} resize-none`
  const monoAreaClass = `${fieldClass} min-h-[16rem] resize-y font-mono`
  const subtleAddButtonClass =
    'inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-[#f1eadc] px-3.5 py-2 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]'
  const deleteButtonClass =
    'rounded-full p-2 text-[#8b5a74] transition-colors hover:bg-[#f6edf1] hover:text-[#6f435b]'
  const sectionHeadingClass = 'text-lg font-semibold tracking-[-0.02em] text-gray-950'
  const sectionIntroClass = 'mt-1 text-sm leading-6 text-gray-600'

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#171717]" />
      </div>
    )
  }

  return (
    <AgentPageShell
      agentName={agentName}
      title="Landing Page"
      description={
        isPublished && slug
          ? <span>Published at <a href={`/a/${slug}`} target="_blank" className="text-[#171717] underline">{`/a/${slug}`}</a></span>
          : 'Not published yet'
      }
      icon={Globe}
      backHref={`/agents/${agentName}/edit`}
      backLabel="Back to Edit"
      badge="Public Profile"
      maxWidthClassName="max-w-[90rem]"
      actions={
        <div className="flex flex-wrap gap-3">
          {isPublished && slug && (
            <a
              href={`/a/${slug}`}
              target="_blank"
              className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-white/80 px-4 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-white"
            >
              <Eye className="h-4 w-4" />
              Preview
            </a>
          )}
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-[1rem] border border-black/10 bg-[#f1eadc] px-4 py-3 text-sm font-semibold text-[#171717] transition-colors hover:bg-[#e8ddc8]"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save draft
          </button>
          <button
            onClick={handlePublish}
            disabled={publishing}
            className="inline-flex items-center gap-2 rounded-[1rem] bg-[#171717] px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-black"
          >
            {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
            {isPublished ? 'Republish' : 'Publish'}
          </button>
        </div>
      }
    >

      {/* Section tabs */}
      <div className="mb-8">
        <AgentPageTabs
          activeId={activeSection}
          onChange={(id) => setActiveSection(id as Section)}
          items={sections.map((section) => ({ id: section.id, label: section.label }))}
        />
      </div>

      {/* Section content */}
      <div className="space-y-6">

        {/* Hero section */}
        {activeSection === 'hero' && (
          <div className="space-y-4">
            <AgentPagePanel className="p-6 sm:p-7">
              <div className="mb-6">
                <h2 className={sectionHeadingClass}>Hero</h2>
                <p className={sectionIntroClass}>Set the first impression, creator details, and call to action for the public profile.</p>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-gray-700">Slug (URL path)</label>
                  <input
                    type="text"
                    value={profile.slug || ''}
                    onChange={e => updateProfile({ slug: e.target.value })}
                    placeholder="my-awesome-agent"
                    className={fieldClass}
                  />
                  <p className="mt-1.5 text-xs text-gray-500">Your page will be at /a/{profile.slug || 'your-slug'}</p>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-gray-700">Tagline</label>
                  <input
                    type="text"
                    value={profile.tagline || ''}
                    onChange={e => updateProfile({ tagline: e.target.value })}
                    placeholder="One-line hook for your agent"
                    className={fieldClass}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-gray-700">Hero Image URL</label>
                  <input
                    type="url"
                    value={profile.hero_image_url || ''}
                    onChange={e => updateProfile({ hero_image_url: e.target.value })}
                    placeholder="https://..."
                    className={fieldClass}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-gray-700">Preview Video URL</label>
                  <input
                    type="url"
                    value={profile.preview_video_url || ''}
                    onChange={e => updateProfile({ preview_video_url: e.target.value })}
                    placeholder="YouTube/Vimeo embed URL"
                    className={fieldClass}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-gray-700">CTA Button Label</label>
                    <input
                      type="text"
                      value={profile.cta_label || ''}
                      onChange={e => updateProfile({ cta_label: e.target.value })}
                      placeholder="Try it free"
                      className={fieldClass}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-semibold text-gray-700">Accent Color</label>
                    <input
                      type="color"
                      value={profile.accent_color || '#ff444f'}
                      onChange={e => updateProfile({ accent_color: e.target.value })}
                      className="h-[50px] w-full cursor-pointer rounded-[1.15rem] border border-black/10 bg-[#fcfaf5] px-2 py-2"
                    />
                  </div>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-gray-700">Creator Display Name</label>
                  <input
                    type="text"
                    value={profile.creator_display_name || ''}
                    onChange={e => updateProfile({ creator_display_name: e.target.value })}
                    placeholder="Your name"
                    className={fieldClass}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-semibold text-gray-700">Creator Bio</label>
                  <textarea
                    value={profile.creator_bio || ''}
                    onChange={e => updateProfile({ creator_bio: e.target.value })}
                    placeholder="Brief bio shown at the bottom of your landing page"
                    rows={2}
                    className={textAreaClass}
                  />
                </div>
              </div>
            </AgentPagePanel>
          </div>
        )}

        {/* Description section */}
        {activeSection === 'description' && (
          <AgentPagePanel className="p-6 sm:p-7">
            <div className="mb-6">
              <h2 className={sectionHeadingClass}>Description</h2>
              <p className={sectionIntroClass}>Write the long-form public profile copy. Markdown formatting is supported.</p>
            </div>
            <textarea
              value={profile.long_description || ''}
              onChange={e => updateProfile({ long_description: e.target.value })}
              placeholder="Describe your agent in detail. What does it do? Who is it for? What can users expect?"
              rows={12}
              className={monoAreaClass}
            />
          </AgentPagePanel>
        )}

        {/* Gallery section */}
        {activeSection === 'gallery' && (
          <AgentPagePanel className="p-6 sm:p-7">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className={sectionHeadingClass}>Gallery Images</h2>
                <p className={sectionIntroClass}>Add screenshots or visuals that support the public story of the agent.</p>
              </div>
              <button
                onClick={addGalleryImage}
                className={subtleAddButtonClass}
              >
                <Plus className="h-4 w-4" /> Add image
              </button>
            </div>
            <div className="space-y-3">
              {(profile.gallery_images || []).map((img, i) => (
                <div key={i} className="flex items-start gap-3 rounded-[1.35rem] border border-black/10 bg-[#fcfaf5] p-4">
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
                      className={fieldClass}
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
                      className={fieldClass}
                    />
                  </div>
                  <button onClick={() => removeGalleryImage(i)} className={`${deleteButtonClass} mt-1`}>
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              {!(profile.gallery_images?.length) && (
                <div className="rounded-[1.5rem] border border-dashed border-black/10 bg-[#fcfaf5] py-10 text-center text-sm text-gray-500">
                  No images yet. Add your first gallery image.
                </div>
              )}
            </div>
          </AgentPagePanel>
        )}

        {/* Examples section */}
        {activeSection === 'examples' && (
          <AgentPagePanel className="p-6 sm:p-7">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h2 className={sectionHeadingClass}>Example Conversations</h2>
                <p className={sectionIntroClass}>Keep examples structured so visitors can quickly understand how the agent responds.</p>
              </div>
              <button
                onClick={addExample}
                className={subtleAddButtonClass}
              >
                <Plus className="h-4 w-4" /> Add example
              </button>
            </div>
            <div className="space-y-4">
              {(profile.example_conversations || []).map((ex, i) => (
                <div key={i} className="rounded-[1.5rem] border border-black/10 bg-[#fcfaf5] p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <input
                      type="text"
                      value={ex.title}
                      onChange={e => {
                        const exs = [...(profile.example_conversations || [])]
                        exs[i] = { ...exs[i], title: e.target.value }
                        updateProfile({ example_conversations: exs })
                      }}
                      placeholder="Conversation title"
                      className="flex-1 border-0 border-b border-black/10 bg-transparent pb-2 text-sm font-semibold text-gray-900 placeholder-gray-400 focus:border-[#79dfbc] focus:outline-none"
                    />
                    <button onClick={() => removeExample(i)} className={deleteButtonClass}>
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
                        className="w-28 rounded-[1rem] border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-gray-700 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[#79dfbc]"
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
                        className={`${fieldClass} py-2.5`}
                      />
                    </div>
                  ))}
                </div>
              ))}
              {!(profile.example_conversations?.length) && (
                <div className="rounded-[1.5rem] border border-dashed border-black/10 bg-[#fcfaf5] py-10 text-center text-sm text-gray-500">
                  No examples yet.
                </div>
              )}
            </div>
          </AgentPagePanel>
        )}

        {/* SEO section */}
        {activeSection === 'seo' && (
          <AgentPagePanel className="p-6 sm:p-7">
            <div className="mb-6">
              <h2 className={sectionHeadingClass}>SEO & Social</h2>
              <p className={sectionIntroClass}>Fine-tune how the public page appears in search engines and previews.</p>
            </div>
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-semibold text-gray-700">Meta Title</label>
                <input
                  type="text"
                  value={profile.seo_title || ''}
                  onChange={e => updateProfile({ seo_title: e.target.value })}
                  placeholder="Page title for search engines"
                  className={fieldClass}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-semibold text-gray-700">Meta Description</label>
                <textarea
                  value={profile.seo_description || ''}
                  onChange={e => updateProfile({ seo_description: e.target.value })}
                  placeholder="Description for search engines (120-160 chars)"
                  rows={3}
                  className={textAreaClass}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-semibold text-gray-700">OG Image URL</label>
                <input
                  type="url"
                  value={profile.og_image_url || ''}
                  onChange={e => updateProfile({ og_image_url: e.target.value })}
                  placeholder="Image shown when shared on social media"
                  className={fieldClass}
                />
              </div>
            </div>
          </AgentPagePanel>
        )}
      </div>
    </AgentPageShell>
  )
}
