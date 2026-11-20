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
    google: 'hover:bg-blush-wash dark:hover:bg-wine/20 border-taupe dark:border-ink-soft',
    microsoft: 'hover:bg-sky-wash dark:hover:bg-azure/20 border-taupe dark:border-ink-soft',
    apple: 'hover:bg-sand dark:hover:bg-ink-soft border-taupe dark:border-ink-soft',
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
          bg-white dark:bg-ink
          border ${providerColors[provider]}
          transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200
          disabled:opacity-50 disabled:cursor-not-allowed
          hover:shadow-md
        `}
      >
        {loading ? (
          <div className="w-5 h-5 border-2 border-taupe border-t-ink-soft rounded-full motion-safe:animate-spin" />
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
        bg-white dark:bg-ink
        border ${providerColors[provider]}
        transition-[color,background-color,border-color,box-shadow,opacity,transform] duration-200
        disabled:opacity-50 disabled:cursor-not-allowed
        hover:shadow-md
      `}
    >
      {loading ? (
        <div className="w-5 h-5 border-2 border-taupe border-t-ink-soft rounded-full motion-safe:animate-spin" />
      ) : (
        <ProviderIcon provider={provider} size="sm" />
      )}
      <span className="text-sm font-medium text-ink-soft dark:text-taupe">
        {loading ? t('connecting') : t('continueWith', { provider: providerNames[provider] })}
      </span>
    </button>
  );
};
