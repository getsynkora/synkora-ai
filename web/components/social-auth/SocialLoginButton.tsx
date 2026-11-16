'use client';

import React from 'react';
import { ProviderIcon } from './ProviderIcon';
import { SocialProvider } from '@/types/social-auth';
import { useTranslations } from 'next-intl';

interface SocialLoginButtonProps {
  provider: SocialProvider;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'full' | 'icon';
}

export const SocialLoginButton: React.FC<SocialLoginButtonProps> = ({
  provider,
  onClick,
  disabled = false,
  loading = false,
  variant = 'icon',
}) => {
  const t = useTranslations('auth.social');
  const providerNames: Record<SocialProvider, string> = {
    google: 'Google',
    microsoft: 'Microsoft',
    apple: 'Apple',
  };

  const providerColors: Record<SocialProvider, string> = {
    google: 'hover:bg-red-50 dark:hover:bg-red-900/20 border-gray-300 dark:border-gray-600',
    microsoft: 'hover:bg-blue-50 dark:hover:bg-blue-900/20 border-gray-300 dark:border-gray-600',
    apple: 'hover:bg-gray-100 dark:hover:bg-gray-700 border-gray-300 dark:border-gray-600',
  };

  if (variant === 'icon') {
    return (
      <button
        onClick={onClick}
        disabled={disabled || loading}
        title={t('continueWith', { provider: providerNames[provider] })}
        className={`
          flex items-center justify-center
          w-12 h-12 rounded-lg
          bg-white dark:bg-gray-800
          border ${providerColors[provider]}
          transition-all duration-200
          disabled:opacity-50 disabled:cursor-not-allowed
          hover:shadow-md
        `}
      >
        {loading ? (
          <div className="w-5 h-5 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
        ) : (
          <ProviderIcon provider={provider} size="sm" />
        )}
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        w-full flex items-center justify-center gap-3
        px-4 py-3 rounded-lg
        bg-white dark:bg-gray-800
        border ${providerColors[provider]}
        transition-all duration-200
        disabled:opacity-50 disabled:cursor-not-allowed
        hover:shadow-md
      `}
    >
      {loading ? (
        <div className="w-5 h-5 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
      ) : (
        <ProviderIcon provider={provider} size="sm" />
      )}
      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
        {loading ? t('connecting') : t('continueWith', { provider: providerNames[provider] })}
      </span>
    </button>
  );
};
