'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import { Apple, ArrowLeft, Bot, Globe, Info, Save, Settings, Smartphone } from 'lucide-react'
import { apiClient } from '@/lib/api/client'

const STORE_TYPES = [
  {
    value: 'google_play',
    label: 'Google Play Store',
    icon: Bot,
    description: 'Android app reviews',
  },
  {
    value: 'apple_app_store',
    label: 'Apple App Store',
    icon: Apple,
    description: 'iOS app reviews',
  },
]

const SYNC_FREQUENCIES = [
  { value: 'hourly', label: 'Hourly', description: 'Check for new reviews every hour' },
  { value: 'daily', label: 'Daily', description: 'Check once per day' },
  { value: 'weekly', label: 'Weekly', description: 'Check once per week' },
  { value: 'manual', label: 'Manual', description: 'Only sync when triggered manually' },
]

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'ja', label: 'Japanese' },
  { value: 'ko', label: 'Korean' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ar', label: 'Arabic' },
  { value: 'hi', label: 'Hindi' },
  { value: 'ru', label: 'Russian' },
]

const COUNTRIES = [
  { value: 'us', label: 'United States' },
  { value: 'gb', label: 'United Kingdom' },
  { value: 'ca', label: 'Canada' },
  { value: 'au', label: 'Australia' },
  { value: 'de', label: 'Germany' },
  { value: 'fr', label: 'France' },
  { value: 'es', label: 'Spain' },
  { value: 'it', label: 'Italy' },
  { value: 'jp', label: 'Japan' },
  { value: 'kr', label: 'South Korea' },
  { value: 'cn', label: 'China' },
  { value: 'in', label: 'India' },
  { value: 'br', label: 'Brazil' },
  { value: 'mx', label: 'Mexico' },
]

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active', description: 'Actively syncing reviews' },
  { value: 'paused', label: 'Paused', description: 'Temporarily stop syncing' },
]

export default function EditAppStoreSourcePage() {
  const params = useParams()
  const router = useRouter()
  const sourceId = params.id as string

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<any>(null)

  const [formData, setFormData] = useState({
    app_name: '',
    sync_frequency: 'daily',
    min_rating: 1,
    languages: ['en'],
    countries: ['us'],
    status: 'active',
  })

  useEffect(() => {
    loadSource()
  }, [sourceId])

  const loadSource = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getAppStoreSource(sourceId)
      setSource(data)
      setFormData({
        app_name: data.app_name || '',
        sync_frequency: data.sync_frequency || 'daily',
        min_rating: data.min_rating || 1,
        languages: data.languages || ['en'],
        countries: data.countries || ['us'],
        status: data.status || 'active',
      })
    } catch (err) {
      console.error('Failed to load source:', err)
      toast.error('Failed to load app source')
      setError(err instanceof Error ? err.message : 'Failed to load app source')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)

    try {
      const payload = {
        app_name: formData.app_name,
        sync_frequency: formData.sync_frequency,
        min_rating: formData.min_rating,
        languages: formData.languages,
        countries: formData.countries,
        status: formData.status,
      }

      await apiClient.updateAppStoreSource(sourceId, payload)
      toast.success('App source updated successfully!')
      router.push(`/app-store-reviews/${sourceId}`)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred'
      setError(errorMessage)
      toast.error(`Failed to update app source: ${errorMessage}`)
    } finally {
      setSaving(false)
    }
  }

  const toggleLanguage = (lang: string) => {
    setFormData(prev => ({
      ...prev,
      languages: prev.languages.includes(lang)
        ? prev.languages.filter(l => l !== lang)
        : [...prev.languages, lang],
    }))
  }

  const toggleCountry = (country: string) => {
    setFormData(prev => ({
      ...prev,
      countries: prev.countries.includes(country)
        ? prev.countries.filter(c => c !== country)
        : [...prev.countries, country],
    }))
  }

  const selectedStore = STORE_TYPES.find(s => s.value === source?.store_type)

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-azure border-t-transparent rounded-full motion-safe:animate-spin mx-auto mb-4" />
          <p className="text-ink-soft">Loading app source…</p>
        </div>
      </div>
    )
  }

  if (!source) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-ink-soft mb-4">App source not found</p>
          <Link
            href="/app-store-reviews"
            className="text-azure hover:text-azure"
          >
            Back to list
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href={`/app-store-reviews/${sourceId}`}
            className="inline-flex items-center gap-2 text-ink-soft hover:text-ink font-medium mb-6 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Details
          </Link>
          
          <div className="flex items-center gap-4 mb-4">
            <div className="p-3 bg-azure rounded-lg shadow-sm">
              <Smartphone className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">
                Edit App Source
              </h1>
              <p className="text-ink-soft mt-1">
                Update configuration for {source.app_name}
              </p>
            </div>
          </div>

          {/* App Info Badge */}
          <div className="flex items-center gap-3 p-4 bg-white rounded-lg border border-line">
            {selectedStore?.icon && <selectedStore.icon className="h-6 w-6" aria-hidden="true" />}
            <div>
              <div className="font-semibold text-ink">{source.app_name}</div>
              <div className="text-sm text-ink-mute">
                {selectedStore?.label} • {source.app_id}
              </div>
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-sand-deep border-l-4 border-ink rounded-lg">
            <p className="text-danger font-medium">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* App Name */}
          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center gap-3 mb-4">
              <Info className="w-5 h-5 text-azure" />
              <h2 className="text-lg font-semibold text-ink">App Information</h2>
            </div>
            
            <div>
              <label className="block text-sm font-semibold text-ink-soft mb-2">
                App Name <span className="text-leaf">*</span>
              </label>
              <input
                type="text"
                required
                value={formData.app_name}
                onChange={(e) => setFormData(prev => ({ ...prev, app_name: e.target.value }))}
                className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-azure focus:border-transparent"
                placeholder="e.g., WhatsApp Messenger"
              />
            </div>
          </div>

          {/* Sync Settings */}
          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center gap-3 mb-4">
              <Settings className="w-5 h-5 text-azure" />
              <h2 className="text-lg font-semibold text-ink">Sync Settings</h2>
            </div>

            <div className="space-y-6">
              {/* Status */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-3">
                  Status <span className="text-leaf">*</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {STATUS_OPTIONS.map((status) => (
                    <button
                      key={status.value}
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, status: status.value }))}
                      className={`p-4 rounded-lg border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-left ${
                        formData.status === status.value
                          ? 'border-azure bg-sky-wash'
                          : 'border-line hover:border-taupe'
                      }`}
                    >
                      <div className="font-semibold text-ink">{status.label}</div>
                      <div className="text-xs text-ink-mute mt-1">{status.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Sync Frequency */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-3">
                  Sync Frequency <span className="text-leaf">*</span>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {SYNC_FREQUENCIES.map((freq) => (
                    <button
                      key={freq.value}
                      type="button"
                      onClick={() => setFormData(prev => ({ ...prev, sync_frequency: freq.value }))}
                      className={`p-4 rounded-lg border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-left ${
                        formData.sync_frequency === freq.value
                          ? 'border-azure bg-sky-wash'
                          : 'border-line hover:border-taupe'
                      }`}
                    >
                      <div className="font-semibold text-ink">{freq.label}</div>
                      <div className="text-xs text-ink-mute mt-1">{freq.description}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Minimum Rating Filter */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-2">
                  Minimum Rating Filter
                </label>
                <select
                  value={formData.min_rating}
                  onChange={(e) => setFormData(prev => ({ ...prev, min_rating: parseInt(e.target.value) }))}
                  className="w-full px-4 py-2 border border-taupe rounded-lg focus:ring-2 focus:ring-azure focus:border-transparent"
                >
                  <option value={1}>1 Star and above (All reviews)</option>
                  <option value={2}>2 Stars and above</option>
                  <option value={3}>3 Stars and above</option>
                  <option value={4}>4 Stars and above</option>
                  <option value={5}>5 Stars only</option>
                </select>
                <p className="text-sm text-ink-mute mt-2">
                  Only collect reviews with this rating or higher
                </p>
              </div>
            </div>
          </div>

          {/* Language & Country Filters */}
          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center gap-3 mb-4">
              <Globe className="w-5 h-5 text-azure" />
              <h2 className="text-lg font-semibold text-ink">Language & Country Filters</h2>
            </div>

            <div className="space-y-6">
              {/* Languages */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-3">
                  Languages <span className="text-leaf">*</span>
                </label>
                <p className="text-sm text-ink-soft mb-3">
                  Select languages to collect reviews in (at least one required)
                </p>
                <div className="grid grid-cols-3 md:grid-cols-4 gap-2">
                  {LANGUAGES.map((lang) => (
                    <button
                      key={lang.value}
                      type="button"
                      onClick={() => toggleLanguage(lang.value)}
                      className={`px-3 py-2 rounded-lg border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-sm ${
                        formData.languages.includes(lang.value)
                          ? 'border-azure bg-sky-wash text-azure'
                          : 'border-line hover:border-taupe text-ink-soft'
                      }`}
                    >
                      {lang.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Countries */}
              <div>
                <label className="block text-sm font-semibold text-ink-soft mb-3">
                  Countries <span className="text-leaf">*</span>
                </label>
                <p className="text-sm text-ink-soft mb-3">
                  Select countries to collect reviews from (at least one required)
                </p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {COUNTRIES.map((country) => (
                    <button
                      key={country.value}
                      type="button"
                      onClick={() => toggleCountry(country.value)}
                      className={`px-3 py-2 rounded-lg border-2 transition-[color,background-color,border-color,box-shadow,opacity,transform] text-sm ${
                        formData.countries.includes(country.value)
                          ? 'border-azure bg-sky-wash text-azure'
                          : 'border-line hover:border-taupe text-ink-soft'
                      }`}
                    >
                      {country.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-between items-center bg-white rounded-lg shadow-sm border border-line p-6">
            <Link
              href={`/app-store-reviews/${sourceId}`}
              className="px-6 py-2 border border-taupe text-ink-soft rounded-lg hover:bg-sand transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={saving || formData.languages.length === 0 || formData.countries.length === 0 || !formData.app_name}
              className="px-6 py-2 bg-azure text-white rounded-lg hover:bg-azure transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full motion-safe:animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-5 h-5" />
                  Save Changes
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
