'use client';

import React from 'react';
import { ProviderIcon } from './ProviderIcon';
import { SocialProvider } from '@/types/social-auth';

interface SocialAuthProviderCardProps {
  provider: SocialProvider;
  isLinked: boolean;
  providerEmail?: string;
  linkedAt?: string;
  onUnlink: () => Promise<void>;
  isUnlinking: boolean;
}

export const SocialAuthProviderCard: React.FC<SocialAuthProviderCardProps> = ({
  provider,
  isLinked,
  providerEmail,
  linkedAt,
  onUnlink,
  isUnlinking,
}) => {
  return (
    <div className="bg-white dark:bg-ink rounded-lg border border-line dark:border-ink-soft p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <ProviderIcon provider={provider} size="lg" />
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-ink dark:text-white capitalize">
                {provider}
              </h3>
              <span
                className={`px-2 py-1 text-xs font-medium rounded-full ${
                  isLinked
                    ? 'bg-leaf-wash text-forest dark:bg-forest dark:text-mint'
                    : 'bg-sand text-ink dark:bg-ink-soft dark:text-taupe'
                }`}
              >
                {isLinked ? 'Linked' : 'Not Linked'}
              </span>
            </div>
            {isLinked && providerEmail && (
              <p className="text-sm text-ink-mute dark:text-ash mt-1">
                {providerEmail}
              </p>
            )}
            {isLinked && linkedAt && (
              <p className="text-xs text-ash dark:text-ink-mute mt-1">
                Linked: {new Date(linkedAt).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isLinked ? (
            <button
              onClick={onUnlink}
              disabled={isUnlinking}
              className="px-3 py-1.5 text-sm font-medium text-leaf hover:text-leaf dark:text-hotpink dark:hover:text-blush hover:bg-blush-wash dark:hover:bg-wine/20 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUnlinking ? 'Unlinking…' : 'Unlink'}
            </button>
          ) : (
            <button
              onClick={() => {
                // Trigger OAuth flow - will be handled by the page
                window.location.href = `/api/v1/auth/social/${provider}`;
              }}
              className="px-3 py-1.5 text-sm font-medium text-azure hover:text-azure dark:text-steel dark:hover:text-steel hover:bg-sky-wash dark:hover:bg-azure/20 rounded-md transition-colors"
            >
              Link Account
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
