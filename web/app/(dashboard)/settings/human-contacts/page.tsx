'use client'

import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import {
  Users,
  Plus,
  Edit,
  Trash2,
  Search,
  Mail,
  MessageSquare,
  Phone,
  AlertCircle,
  X,
  CheckCircle
} from 'lucide-react'
import { apiClient } from '@/lib/api/client'

interface HumanContact {
  id: string
  name: string
  email: string
  slack_user_id: string
  slack_workspace_id: string
  whatsapp_number: string
  preferred_channel: string
  is_active: boolean
  timezone: string
  notification_preferences: string
  created_at: string
  updated_at: string
}

const CHANNEL_OPTIONS = [
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'slack', label: 'Slack', icon: MessageSquare },
  { value: 'whatsapp', label: 'WhatsApp', icon: Phone },
]

const NOTIFICATION_OPTIONS = [
  { value: 'all', label: 'All Notifications' },
  { value: 'urgent_only', label: 'Urgent Only' },
  { value: 'none', label: 'None' },
]

export default function HumanContactsPage() {
  const [contacts, setContacts] = useState<HumanContact[]>([])
  const [filteredContacts, setFilteredContacts] = useState<HumanContact[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState<HumanContact | null>(null)
  const [deleteModal, setDeleteModal] = useState<{ show: boolean; contact: HumanContact | null }>({
    show: false,
    contact: null,
  })
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    slack_user_id: '',
    slack_workspace_id: '',
    whatsapp_number: '',
    preferred_channel: 'email',
    is_active: true,
    timezone: 'UTC',
    notification_preferences: 'all',
  })

  useEffect(() => {
    fetchContacts()
  }, [])

  useEffect(() => {
    filterContacts()
  }, [searchQuery, contacts])

  const fetchContacts = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getHumanContacts()
      setContacts(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      toast.error('Failed to load contacts')
    } finally {
      setLoading(false)
    }
  }

  const filterContacts = () => {
    let filtered = contacts
    if (searchQuery) {
      filtered = filtered.filter(contact =>
        contact.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contact.email?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    setFilteredContacts(filtered)
  }

  const openCreateModal = () => {
    setFormData({
      name: '',
      email: '',
      slack_user_id: '',
      slack_workspace_id: '',
      whatsapp_number: '',
      preferred_channel: 'email',
      is_active: true,
      timezone: 'UTC',
      notification_preferences: 'all',
    })
    setShowCreateModal(true)
  }

  const openEditModal = (contact: HumanContact) => {
    setFormData({
      name: contact.name,
      email: contact.email || '',
      slack_user_id: contact.slack_user_id || '',
      slack_workspace_id: contact.slack_workspace_id || '',
      whatsapp_number: contact.whatsapp_number || '',
      preferred_channel: contact.preferred_channel || 'email',
      is_active: contact.is_active,
      timezone: contact.timezone || 'UTC',
      notification_preferences: contact.notification_preferences || 'all',
    })
    setShowEditModal(contact)
  }

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Name is required')
      return
    }

    setSaving(true)
    try {
      if (showEditModal) {
        await apiClient.updateHumanContact(showEditModal.id, formData)
        toast.success('Contact updated successfully')
        setShowEditModal(null)
      } else {
        await apiClient.createHumanContact(formData)
        toast.success('Contact created successfully')
        setShowCreateModal(false)
      }
      fetchContacts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save contact')
    } finally {
      setSaving(false)
    }
  }

  const openDeleteModal = (contact: HumanContact) => {
    setDeleteModal({ show: true, contact })
  }

  const closeDeleteModal = () => {
    setDeleteModal({ show: false, contact: null })
  }

  const confirmDelete = async () => {
    if (!deleteModal.contact) return

    setDeleting(true)
    try {
      await apiClient.deleteHumanContact(deleteModal.contact.id)
      toast.success(`"${deleteModal.contact.name}" has been deleted`)
      closeDeleteModal()
      fetchContacts()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setDeleting(false)
    }
  }

  const getChannelIcon = (channel: string) => {
    const option = CHANNEL_OPTIONS.find(o => o.value === channel)
    const Icon = option?.icon || Mail
    return <Icon className="w-4 h-4" />
  }

  if (loading) {
    return (
      <div className="dashboard-settings-page flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading contacts...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-settings-page min-h-screen p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6 md:mb-8">
          <div className="flex items-center justify-between gap-3 mb-4 md:mb-6">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Human Contacts</h1>
              <p className="text-gray-600 mt-1 text-sm hidden sm:block">
                Manage human team members for agent escalations
              </p>
            </div>
            <button
              onClick={openCreateModal}
              className="inline-flex items-center gap-2 px-4 py-2 md:px-5 md:py-2.5 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-xl transition-all shadow-sm hover:shadow-md font-medium text-sm flex-shrink-0"
            >
              <Plus className="w-4 h-4 md:w-5 md:h-5" />
              <span className="hidden sm:inline">Add Contact</span>
              <span className="sm:hidden">Add</span>
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 md:gap-4 mb-4 md:mb-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-red-100 rounded-xl">
                  <Users className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Total Contacts</p>
                  <p className="text-2xl font-bold text-gray-900">{contacts.length}</p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-green-100 rounded-xl">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Active</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {contacts.filter(c => c.is_active).length}
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-100 rounded-xl">
                  <MessageSquare className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Slack Connected</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {contacts.filter(c => c.slack_user_id).length}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Search */}
          {contacts.length > 0 && (
            <div className="relative">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search contacts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-transparent shadow-sm"
              />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <p className="text-red-700">{error}</p>
            </div>
          </div>
        )}

        {/* Contacts Grid */}
        {filteredContacts.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-12 text-center">
            <div className="w-32 h-32 mx-auto mb-6 relative">
              <div className="absolute inset-0 bg-gradient-to-br from-red-100 to-red-50 rounded-2xl transform rotate-6"></div>
              <div className="absolute inset-0 bg-white rounded-2xl shadow-sm border border-gray-100 flex items-center justify-center">
                <Users className="w-12 h-12 text-red-500" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              {contacts.length === 0 ? 'No contacts yet' : 'No results found'}
            </h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              {contacts.length === 0
                ? 'Add human contacts so your AI agents can escalate issues to the right people.'
                : 'Try adjusting your search.'}
            </p>
            {contacts.length === 0 && (
              <button
                onClick={openCreateModal}
                className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white rounded-xl transition-all shadow-sm hover:shadow-md font-medium"
              >
                <Plus className="w-5 h-5" />
                Add Contact
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredContacts.map((contact) => (
              <div
                key={contact.id}
                className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-all hover:border-red-200 group"
              >
                <div className="p-5">
                  <div className="flex items-start gap-3 mb-4">
                    <div className="p-2.5 bg-red-100 rounded-xl group-hover:bg-red-200 transition-colors">
                      <Users className="w-5 h-5 text-red-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-gray-900 truncate">
                        {contact.name}
                      </h3>
                      <p className="text-sm text-gray-500 truncate">
                        {contact.email || 'No email'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mb-4 flex-wrap">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                      contact.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${contact.is_active ? 'bg-emerald-500' : 'bg-gray-400'}`}></span>
                      {contact.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                      {getChannelIcon(contact.preferred_channel)}
                      {CHANNEL_OPTIONS.find(o => o.value === contact.preferred_channel)?.label || contact.preferred_channel}
                    </span>
                  </div>

                  <div className="text-xs text-gray-500 mb-4 space-y-1">
                    {contact.slack_user_id && (
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-3.5 h-3.5" />
                        <span className="truncate">Slack: {contact.slack_user_id}</span>
                      </div>
                    )}
                    {contact.whatsapp_number && (
                      <div className="flex items-center gap-2">
                        <Phone className="w-3.5 h-3.5" />
                        <span>{contact.whatsapp_number}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => openEditModal(contact)}
                      className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                      Edit
                    </button>
                    <button
                      onClick={() => openDeleteModal(contact)}
                      className="inline-flex items-center justify-center px-3 py-2.5 text-sm font-medium text-red-600 bg-red-50 rounded-lg hover:bg-red-100 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || showEditModal) && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-100 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                {showEditModal ? 'Edit Contact' : 'Add Contact'}
              </h3>
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(null)
                }}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="John Doe"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="john@example.com"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Slack User ID</label>
                  <input
                    type="text"
                    value={formData.slack_user_id}
                    onChange={(e) => setFormData({ ...formData, slack_user_id: e.target.value })}
                    placeholder="U1234567890"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Slack Workspace ID</label>
                  <input
                    type="text"
                    value={formData.slack_workspace_id}
                    onChange={(e) => setFormData({ ...formData, slack_workspace_id: e.target.value })}
                    placeholder="T1234567890"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">WhatsApp Number</label>
                  <input
                    type="text"
                    value={formData.whatsapp_number}
                    onChange={(e) => setFormData({ ...formData, whatsapp_number: e.target.value })}
                    placeholder="+1234567890"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
                  <input
                    type="text"
                    value={formData.timezone}
                    onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                    placeholder="America/New_York"
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Channel</label>
                  <select
                    value={formData.preferred_channel}
                    onChange={(e) => setFormData({ ...formData, preferred_channel: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  >
                    {CHANNEL_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Notifications</label>
                  <select
                    value={formData.notification_preferences}
                    onChange={(e) => setFormData({ ...formData, notification_preferences: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent"
                  >
                    {NOTIFICATION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500"
                />
                <label htmlFor="is_active" className="text-sm text-gray-700">
                  Active (can receive escalations)
                </label>
              </div>
            </div>

            <div className="sticky bottom-0 bg-white border-t border-gray-100 px-6 py-4 flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(null)
                }}
                disabled={saving}
                className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {saving ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  showEditModal ? 'Update Contact' : 'Add Contact'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteModal.show && deleteModal.contact && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2.5 bg-red-100 rounded-xl">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Delete Contact</h3>
            </div>

            <p className="text-gray-600 mb-6">
              Are you sure you want to delete <span className="font-semibold text-gray-900">"{deleteModal.contact.name}"</span>?
              This action cannot be undone.
            </p>

            <div className="flex gap-3 justify-end">
              <button
                onClick={closeDeleteModal}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleting}
                className="px-4 py-2.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {deleting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
