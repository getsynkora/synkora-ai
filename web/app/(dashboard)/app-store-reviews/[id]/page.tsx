'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import toast from 'react-hot-toast'
import {
  Smartphone,
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Star,
  MessageSquare,
  Calendar,
  RefreshCw,
  Settings,
  BarChart3,
  AlertCircle,
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

export default function AppStoreSourceDetailsPage() {
  const params = useParams()
  const sourceId = params.id as string

  const [source, setSource] = useState<any>(null)
  const [analytics, setAnalytics] = useState<any>(null)
  const [reviews, setReviews] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState('daily')

  useEffect(() => {
    loadData()
  }, [sourceId, selectedPeriod])

  const loadData = async () => {
    try {
      setLoading(true)
      const [sourceData, insightsData, reviewsData] = await Promise.all([
        apiClient.getAppStoreSource(sourceId),
        apiClient.getAppStoreInsights(sourceId, { period: selectedPeriod }),
        apiClient.getAppStoreReviews(sourceId, { limit: 10 }),
      ])
      setSource(sourceData)
      setAnalytics(insightsData)
      // Handle both array response and object with reviews property
      const reviewsList = Array.isArray(reviewsData) 
        ? reviewsData 
        : ((reviewsData as any)?.reviews || [])
      setReviews(reviewsList)
    } catch (err) {
      console.error('Failed to load data:', err)
      toast.error('Failed to load app source details')
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    try {
      setSyncing(true)
      await apiClient.syncAppStoreReviews(sourceId)
      toast.success('Sync started successfully')
      setTimeout(loadData, 2000)
    } catch (err) {
      console.error('Failed to sync:', err)
      toast.error('Failed to start sync')
    } finally {
      setSyncing(false)
    }
  }

  const getRatingColor = (rating: number) => {
    if (rating >= 4) return 'text-leaf'
    if (rating >= 3) return 'text-warn'
    return 'text-danger'
  }

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'positive':
        return 'bg-leaf-wash text-forest'
      case 'negative':
        return 'bg-blush-wash text-wine'
      case 'neutral':
        return 'bg-sand text-ink'
      default:
        return 'bg-sky-wash text-azure'
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-azure border-t-transparent rounded-full motion-safe:animate-spin mx-auto mb-4" />
          <p className="text-ink-soft">Loading app source details…</p>
        </div>
      </div>
    )
  }

  if (!source) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-ash mx-auto mb-4" />
          <p className="text-ink-soft">App source not found</p>
          <Link
            href="/app-store-reviews"
            className="mt-4 inline-block text-azure hover:text-azure"
          >
            Back to list
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/app-store-reviews"
            className="inline-flex items-center gap-2 text-ink-soft hover:text-ink font-medium mb-6 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to App Store Reviews
          </Link>

          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-azure rounded-lg shadow-sm">
                <Smartphone className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">{source.app_name}</h1>
                <div className="flex items-center gap-4 mt-2 text-sm text-ink-soft">
                  <span className="flex items-center gap-1">
                    {source.store_type === 'google_play' ? 'Google Play' : 'App Store'}
                  </span>
                  <span>•</span>
                  <span>{source.app_id}</span>
                  <span>•</span>
                  <span className="capitalize">{source.status}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleSync}
                disabled={syncing}
                className="flex items-center gap-2 px-4 py-2 bg-azure text-white rounded-lg hover:bg-azure transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${syncing ? 'motion-safe:animate-spin' : ''}`} />
                {syncing ? 'Syncing…' : 'Sync Now'}
              </button>
              <Link
                href={`/app-store-reviews/${sourceId}/edit`}
                className="flex items-center gap-2 px-4 py-2 border border-taupe text-ink-soft rounded-lg hover:bg-sand transition-colors"
              >
                <Settings className="w-4 h-4" />
                Edit
              </Link>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-ink-soft">Total Reviews</span>
              <MessageSquare className="w-5 h-5 text-azure" />
            </div>
            <div className="text-xl sm:text-3xl font-bold text-ink">
              {source.total_reviews_collected?.toLocaleString() || 0}
            </div>
            {analytics?.review_volume_change !== undefined && (
              <div className="flex items-center gap-1 mt-2 text-sm">
                {analytics.review_volume_change >= 0 ? (
                  <TrendingUp className="w-4 h-4 text-leaf" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-leaf" />
                )}
                <span
                  className={
                    analytics.review_volume_change >= 0 ? 'text-leaf' : 'text-leaf'
                  }
                >
                  {Math.abs(analytics.review_volume_change).toFixed(1)}%
                </span>
                <span className="text-ink-mute">vs last period</span>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-ink-soft">Average Rating</span>
              <Star className="w-5 h-5 text-warn" />
            </div>
            <div className={`text-xl sm:text-3xl font-bold ${getRatingColor(analytics?.average_rating || 0)}`}>
              {analytics?.average_rating?.toFixed(1) || 'N/A'}
            </div>
            {analytics?.rating_change !== undefined && (
              <div className="flex items-center gap-1 mt-2 text-sm">
                {analytics.rating_change >= 0 ? (
                  <TrendingUp className="w-4 h-4 text-leaf" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-leaf" />
                )}
                <span className={analytics.rating_change >= 0 ? 'text-leaf' : 'text-leaf'}>
                  {analytics.rating_change >= 0 ? '+' : ''}
                  {analytics.rating_change?.toFixed(2)}
                </span>
                <span className="text-ink-mute">vs last period</span>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-ink-soft">Sentiment</span>
              <BarChart3 className="w-5 h-5 text-plum" />
            </div>
            <div className="text-xl sm:text-3xl font-bold text-ink capitalize">
              {analytics?.sentiment_trend || 'N/A'}
            </div>
            {analytics?.sentiment_distribution && (
              <div className="flex gap-2 mt-2">
                {Object.entries(analytics.sentiment_distribution).map(([key, value]: [string, any]) => (
                  <div key={key} className="text-xs">
                    <span className="capitalize">{key}:</span> {value}%
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-ink-soft">Last Sync</span>
              <Calendar className="w-5 h-5 text-ink-soft" />
            </div>
            <div className="text-lg font-semibold text-ink">
              {source.last_sync_at
                ? new Date(source.last_sync_at).toLocaleDateString()
                : 'Never'}
            </div>
            <div className="text-sm text-ink-mute mt-1">
              Next: {source.next_sync_at ? new Date(source.next_sync_at).toLocaleDateString() : 'N/A'}
            </div>
          </div>
        </div>

        {/* Period Selector */}
        <div className="bg-white rounded-lg shadow-sm border border-line p-4 mb-6">
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-ink-soft">Time Period:</span>
            <div className="flex gap-2">
              {['daily', 'weekly', 'monthly'].map((period) => (
                <button
                  key={period}
                  onClick={() => setSelectedPeriod(period)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedPeriod === period
                      ? 'bg-azure text-white'
                      : 'bg-sand text-ink-soft hover:bg-line'
                  }`}
                >
                  {period.charAt(0).toUpperCase() + period.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Rating Distribution */}
        {analytics?.rating_distribution && (
          <div className="bg-white rounded-lg shadow-sm border border-line p-6 mb-6">
            <h2 className="text-xl font-semibold text-ink mb-4">Rating Distribution</h2>
            <div className="space-y-3">
              {[5, 4, 3, 2, 1].map((rating) => {
                const count = analytics.rating_distribution[rating] || 0
                const total = Object.values(analytics.rating_distribution).reduce(
                  (a: any, b: any) => a + b,
                  0
                ) as number
                const percentage = total > 0 ? (count / total) * 100 : 0

                return (
                  <div key={rating} className="flex items-center gap-4">
                    <div className="flex items-center gap-1 w-20">
                      <span className="text-sm font-medium">{rating}</span>
                      <Star className="w-4 h-4 text-warn fill-warn" />
                    </div>
                    <div className="flex-1 bg-line rounded-full h-6 overflow-hidden">
                      <div
                        className="bg-azure h-full rounded-full transition-[color,background-color,border-color,box-shadow,opacity,transform]"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                    <span className="text-sm text-ink-soft w-20 text-right">
                      {count} ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Top Issues & Features */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {analytics?.top_issues && analytics.top_issues.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-line p-6">
              <h2 className="text-xl font-semibold text-ink mb-4">Top Issues</h2>
              <div className="space-y-3">
                {analytics.top_issues.slice(0, 5).map((issue: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="text-sm text-ink-soft">{issue.name}</span>
                    <span className="text-sm font-medium text-leaf">{issue.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {analytics?.top_features && analytics.top_features.length > 0 && (
            <div className="bg-white rounded-lg shadow-sm border border-line p-6">
              <h2 className="text-xl font-semibold text-ink mb-4">Top Features</h2>
              <div className="space-y-3">
                {analytics.top_features.slice(0, 5).map((feature: any, idx: number) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="text-sm text-ink-soft">{feature.name}</span>
                    <span className="text-sm font-medium text-leaf">{feature.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Recent Reviews */}
        {reviews.length > 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-line p-6">
            <h2 className="text-xl font-semibold text-ink mb-4">Recent Reviews</h2>
            <div className="space-y-4">
              {reviews.map((review: any) => (
                <div key={review.id} className="border-b border-line pb-4 last:border-0">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="flex">
                        {[...Array(5)].map((_, i) => (
                          <Star
                            key={i}
                            className={`w-4 h-4 ${
                              i < review.rating
                                ? 'text-warn fill-warn'
                                : 'text-taupe'
                            }`}
                          />
                        ))}
                      </div>
                      <span className="text-sm font-medium text-ink">
                        {review.author_name}
                      </span>
                    </div>
                    <span className="text-xs text-ink-mute">
                      {new Date(review.review_date).toLocaleDateString()}
                    </span>
                  </div>
                  {review.title && (
                    <h3 className="font-medium text-ink mb-1">{review.title}</h3>
                  )}
                  <p className="text-sm text-ink-soft mb-2">{review.content}</p>
                  {review.sentiment && (
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-medium ${getSentimentColor(
                        review.sentiment
                      )}`}
                    >
                      {review.sentiment}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
