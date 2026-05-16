'use client';

import { useState, useEffect } from 'react';
import { TeamMembersList } from '@/components/team/TeamMembersList';
import { TeamInviteForm } from '@/components/team/TeamInviteForm';
import { useTeam } from '@/hooks/useTeam';
import type { TeamMember, TeamInvitation } from '@/types/team';

export default function TeamSettingsPage() {
  const {
    error,
    success,
    clearMessages,
    getTeamMembers,
    inviteTeamMember,
    updateTeamMember,
    removeTeamMember,
    getPendingInvitations,
    resendInvitation,
    cancelInvitation,
    getDomainSettings,
    updateDomainSettings,
  } = useTeam();

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [invitations, setInvitations] = useState<TeamInvitation[]>([]);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // Domain settings state
  const [domainSettings, setDomainSettings] = useState<{ domain: string | null; auto_assign_domain_users: boolean }>({
    domain: null,
    auto_assign_domain_users: false,
  });
  const [domainInput, setDomainInput] = useState('');
  const [autoAssignEnabled, setAutoAssignEnabled] = useState(false);
  const [isSavingDomain, setIsSavingDomain] = useState(false);

  // TODO: Get actual tenant ID from auth context
  const tenantId = 'default-tenant';

  useEffect(() => {
    loadData();
  }, []);

  // Auto-dismiss success message after 5 seconds
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => clearMessages(), 5000);
      return () => clearTimeout(timer);
    }
  }, [success, clearMessages]);

  const loadData = async () => {
    const [membersData, invitationsData, domainData] = await Promise.all([
      getTeamMembers(tenantId),
      getPendingInvitations(tenantId),
      getDomainSettings(),
    ]);
    setMembers(membersData);
    setInvitations(Array.isArray(invitationsData) ? invitationsData : []);
    if (domainData) {
      setDomainSettings(domainData);
      setDomainInput(domainData.domain || '');
      setAutoAssignEnabled(domainData.auto_assign_domain_users);
    }
    setIsInitialLoading(false);
  };

  const handleResendInvitation = async (invitationId: string) => {
    const result = await resendInvitation(tenantId, invitationId);
    if (result) {
      await loadData();
    }
  };

  const handleCancelInvitation = async (invitationId: string) => {
    if (confirm('Are you sure you want to cancel this invitation?')) {
      const result = await cancelInvitation(tenantId, invitationId);
      if (result) {
        await loadData();
      }
    }
  };

  const handleSaveDomainSettings = async () => {
    setIsSavingDomain(true);
    const result = await updateDomainSettings({
      domain: domainInput.trim() || null,
      auto_assign_domain_users: autoAssignEnabled,
    });
    if (result) {
      setDomainSettings({
        domain: domainInput.trim() || null,
        auto_assign_domain_users: autoAssignEnabled,
      });
    }
    setIsSavingDomain(false);
  };

  if (isInitialLoading) {
    return (
      <div className="dashboard-settings-page flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
      </div>
    );
  }

  return (
    <div className="dashboard-settings-page min-h-screen">
      <div className="max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-6">
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">Team Management</h1>
              <p className="mt-1 text-sm text-gray-600">
                Manage your team members and their roles
              </p>
            </div>
            <button
              onClick={() => setShowInviteForm(!showInviteForm)}
              className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all flex items-center text-xs font-medium shadow-sm"
            >
              <svg
                className="w-4 h-4 mr-1.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Invite Member
            </button>
          </div>
        </div>

        {/* Success Message */}
        {success && (
          <div className="mb-5 bg-green-50 border border-green-200 rounded-lg p-3.5 flex items-center justify-between">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <p className="text-sm text-green-700">{success}</p>
            </div>
            <button onClick={clearMessages} className="text-green-500 hover:text-green-700">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mb-5 bg-red-50 border border-red-200 rounded-lg p-3.5 flex items-center justify-between">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <p className="text-sm text-red-600">{error}</p>
            </div>
            <button onClick={clearMessages} className="text-red-500 hover:text-red-700">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        )}

        {/* Invite Form */}
        {showInviteForm && (
          <div className="mb-5">
            <TeamInviteForm
              onInvite={async (email, role) => {
                const result = await inviteTeamMember(tenantId, { email, role });
                if (result) {
                  setShowInviteForm(false);
                  await loadData();
                }
              }}
              onCancel={() => setShowInviteForm(false)}
            />
          </div>
        )}

        {/* Pending Invitations */}
        {invitations.length > 0 && (
          <div className="mb-6 bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-yellow-50">
              <h3 className="text-lg font-medium text-gray-900 flex items-center">
                <svg className="w-5 h-5 text-yellow-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                Pending Invitations
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                {invitations.length} pending {invitations.length === 1 ? 'invitation' : 'invitations'}
              </p>
            </div>
            <ul className="divide-y divide-gray-200">
              {invitations.map((invitation) => (
                <li key={invitation.id} className="px-6 py-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{invitation.email}</p>
                      <div className="flex items-center mt-1 text-xs text-gray-500 space-x-3">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 capitalize">
                          {invitation.role}
                        </span>
                        <span>Invited by {invitation.invited_by_name || 'Unknown'}</span>
                        <span>Expires {new Date(invitation.expires_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleResendInvitation(invitation.id)}
                        className="px-3 py-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md transition-colors"
                      >
                        Resend
                      </button>
                      <button
                        onClick={() => handleCancelInvitation(invitation.id)}
                        className="px-3 py-1.5 text-xs font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded-md transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Team Members List */}
        <TeamMembersList
          members={members}
          currentUserId="current-user-id" // TODO: Get from auth context
          canManageTeam={true} // TODO: Get from permissions
          onUpdateRole={async (memberId, role) => {
            const result = await updateTeamMember(tenantId, memberId, { role });
            if (result) {
              await loadData();
            }
          }}
          onRemoveMember={async (memberId) => {
            const success = await removeTeamMember(tenantId, memberId);
            if (success) {
              await loadData();
            }
          }}
        />

        {/* Team Stats */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0 bg-red-100 rounded-md p-2.5">
                <svg
                  className="h-5 w-5 text-red-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                  />
                </svg>
              </div>
              <div className="ml-3.5">
                <p className="text-xs font-medium text-gray-500">Total Members</p>
                <p className="text-2xl font-semibold text-gray-900">{members?.length || 0}</p>
              </div>
            </div>
          </div>

          <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0 bg-emerald-100 rounded-md p-2.5">
                <svg
                  className="h-5 w-5 text-emerald-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
              </div>
              <div className="ml-3.5">
                <p className="text-xs font-medium text-gray-500">Admins</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {members?.filter(m => m.role === 'admin' || m.role === 'owner').length || 0}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white shadow-sm border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0 bg-yellow-100 rounded-md p-2.5">
                <svg
                  className="h-5 w-5 text-yellow-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <div className="ml-3.5">
                <p className="text-xs font-medium text-gray-500">Pending Invites</p>
                <p className="text-2xl font-semibold text-gray-900">{invitations?.length || 0}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Domain Auto-Assignment Settings */}
        <div className="mt-6 bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900 flex items-center">
              <svg className="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
              Domain Settings
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Configure automatic team assignment for users with your company email domain
            </p>
          </div>
          <div className="px-6 py-4 space-y-4">
            <div>
              <label htmlFor="domain" className="block text-sm font-medium text-gray-700 mb-1">
                Company Domain
              </label>
              <div className="flex items-center gap-2">
                <span className="text-gray-500">@</span>
                <input
                  type="text"
                  id="domain"
                  value={domainInput}
                  onChange={(e) => setDomainInput(e.target.value)}
                  placeholder="example.com"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-red-500 focus:border-red-500 text-sm"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Users who sign up with this email domain will be automatically added to this team
              </p>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="auto-assign"
                checked={autoAssignEnabled}
                onChange={(e) => setAutoAssignEnabled(e.target.checked)}
                className="h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300 rounded"
              />
              <label htmlFor="auto-assign" className="ml-2 block text-sm text-gray-700">
                Enable automatic team assignment for new users
              </label>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={handleSaveDomainSettings}
                disabled={isSavingDomain}
                className="px-4 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all text-sm font-medium shadow-sm disabled:opacity-50"
              >
                {isSavingDomain ? 'Saving...' : 'Save Domain Settings'}
              </button>
            </div>
          </div>
        </div>

        {/* Help Text */}
        <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-4 w-4 text-red-500"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-xs font-medium text-red-800">About Team Roles</h3>
              <div className="mt-2 text-xs text-red-700">
                <ul className="list-disc list-inside space-y-1">
                  <li><strong>Owner:</strong> Full access to all features and settings</li>
                  <li><strong>Admin:</strong> Can manage team members and most settings</li>
                  <li><strong>Editor:</strong> Can create and edit content</li>
                  <li><strong>Member:</strong> Can view and use agents</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
