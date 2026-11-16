'use client'

import { useEffect } from 'react'
import { useAuthStore } from '@/lib/store/authStore'
import { secureStorage } from '@/lib/auth/secure-storage'
import { LanguageSwitcher } from '@/components/i18n/LanguageSwitcher'

// Initialize session for auth pages so signin can redirect already-authenticated users.
export function AuthShell({
  children,
}: {
  children: React.ReactNode
}) {
  const fetchUser = useAuthStore((state) => state.fetchUser)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      secureStorage.migrateFromLocalStorage()
      fetchUser()
    }
     
  }, [])

  return (
    <>
      <div className="fixed right-4 top-4 z-50">
        <LanguageSwitcher />
      </div>
      {children}
    </>
  )
}
