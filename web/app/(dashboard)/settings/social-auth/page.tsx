'use client';

import { useEffect, useState } from 'react';
import { useSocialAuth } from '@/hooks/useSocialAuth';
import LoadingSpinner from '@/components/common/LoadingSpinner';
import ErrorAlert from '@/components/common/ErrorAlert';
import { SocialAuthProviderCard } from '@/components/social-auth';
import type { SocialProvider } from '@/types/social-auth';

const AVAILABLE_PROVIDERS: SocialProvider[] = ['google', 'microsoft', 'apple'];

export default function SocialAuthPage() {
  const {
    linkedProviders,
    loading,
    error,
    fetchLinkedProviders,
    unlinkSocialProvider,
    clearError,
  } = useSocialAuth();

  const [unlinking, setUnlinking] = useState<SocialProvider | null>(null);

  useEffect(() => {
    fetchLinkedProviders();
  }, [fetchLinkedProviders]);

  const handleUnlink = async (provider: SocialProvider) => {
    if (!confirm(`Are you sure you want to unlink your ${provider} account?`)) {
      return;
    }

    try {
      setUnlinking(provider);
      await unlinkSocialProvider(provider);
    } catch (err) {
      console.error('Failed to unlink provider:', err);
    } finally {
      setUnlinking(null);
    }
  };

  const isProviderLinked = (provider: SocialProvider) => {
    return linkedProviders.some(p => p.provider === provider);
  };

  const getProviderData = (provider: SocialProvider) => {
    return linkedProviders.find(p => p.provider === provider);
  };

  if (loading && linkedProviders.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-extrabold text-ink tracking-tight">Social Authentication</h1>
        <p className="mt-2 text-sm text-ink-soft">
          Link your social accounts to enable quick sign-in and account recovery.
        </p>
      </div>

      {/* Error Alert */}
      {error && (
        <ErrorAlert
          message={error}
          onDismiss={clearError}
        />
      )}

      {/* Admin Configuration Notice */}
      <div className="bg-sky-wash border border-sky-wash rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg aria-hidden="true" className="h-5 w-5 text-steel" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-azure">
              Administrator Configuration Required
            </h3>
            <div className="mt-2 text-sm text-azure">
              <p>
                Social authentication providers must be configured by your system administrator
                before they can be used. Contact your admin to enable Google, Microsoft, or Apple sign-in.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Linked Accounts */}
      <div>
        <h2 className="text-lg font-semibold text-ink mb-4">Linked Accounts</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {AVAILABLE_PROVIDERS.map((provider) => {
            const isLinked = isProviderLinked(provider);
            const providerData = getProviderData(provider);
            const isUnlinking = unlinking === provider;

            return (
              <SocialAuthProviderCard
                key={provider}
                provider={provider}
                isLinked={isLinked}
                providerEmail={providerData?.email}
                linkedAt={providerData?.linked_at}
                onUnlink={() => handleUnlink(provider)}
                isUnlinking={isUnlinking}
              />
            );
          })}
        </div>
      </div>

      {/* Help Text */}
      <div className="bg-cream border border-line rounded-lg p-4">
        <h3 className="text-sm font-medium text-ink mb-2">
          About Social Authentication
        </h3>
        <ul className="text-sm text-ink-soft space-y-1 list-disc list-inside">
          <li>Link multiple social accounts to your profile for flexible sign-in options</li>
          <li>You can unlink accounts at any time (ensure you have at least one sign-in method)</li>
          <li>Linked accounts share the same profile and settings</li>
          <li>Your email address from social providers is used for account matching</li>
        </ul>
      </div>
    </div>
  );
}
