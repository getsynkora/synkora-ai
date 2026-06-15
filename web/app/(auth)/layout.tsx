'use client'

import { useEffect } from 'react'
import { useAuthStore } from '@/lib/store/authStore'
import { secureStorage } from '@/lib/auth/secure-storage'

// Initialize session for auth pages so signin can redirect already-authenticated users.
export default function AuthLayout({
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

  return <>{children}</>
}
