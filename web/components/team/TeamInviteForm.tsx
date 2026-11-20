'use client';

import { useState } from 'react';
import { UserRole, ROLE_LABELS, ROLE_DESCRIPTIONS } from '@/types/team';

interface TeamInviteFormProps {
  onInvite: (email: string, role: UserRole) => Promise<void>;
  onCancel?: () => void;
  isLoading?: boolean;
}

export function TeamInviteForm({ onInvite, onCancel, isLoading = false }: TeamInviteFormProps) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<UserRole>('member');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate email
    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    try {
      await onInvite(email, role);
      // Reset form on success
      setEmail('');
      setRole('member');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invitation');
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-lg font-medium text-ink mb-4">Invite Team Member</h3>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Email Input */}
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-ink-soft mb-1">
            Email Address
          </label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="colleague@example.com"
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
            disabled={isLoading}
            required
          />
        </div>

        {/* Role Selection */}
        <div>
          <label htmlFor="role" className="block text-sm font-medium text-ink-soft mb-1">
            Role
          </label>
          <select
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="w-full px-3 py-2 border border-taupe rounded-md focus:outline-none focus:ring-2 focus:ring-azure"
            disabled={isLoading}
          >
            <option value="admin">{ROLE_LABELS.admin}</option>
            <option value="editor">{ROLE_LABELS.editor}</option>
            <option value="member">{ROLE_LABELS.member}</option>
          </select>
          <p className="mt-1 text-sm text-ink-mute">
            {ROLE_DESCRIPTIONS[role]}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-blush-wash border border-blush rounded-md p-3">
            <p className="text-sm text-wine">{error}</p>
          </div>
        )}

        {/* Submit Buttons */}
        <div className="flex justify-end gap-3">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={isLoading}
              className="px-4 py-2 bg-line text-ink-soft rounded-md hover:bg-taupe focus:outline-none focus:ring-2 focus:ring-ash disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={isLoading}
            className="px-4 py-2 bg-leaf text-white rounded-md hover:bg-forest focus:outline-none focus:ring-2 focus:ring-leaf disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Sending…' : 'Send Invitation'}
          </button>
        </div>
      </form>

      {/* Info Box */}
      <div className="mt-6 bg-sky-wash border border-sky-wash rounded-md p-4">
        <h4 className="text-sm font-medium text-azure mb-2">About Invitations</h4>
        <ul className="text-sm text-azure space-y-1">
          <li>• Invitations are sent via email</li>
          <li>• They expire after 7 days</li>
          <li>• Recipients must have or create an account to accept</li>
        </ul>
      </div>
    </div>
  );
}
