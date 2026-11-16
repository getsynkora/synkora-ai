import { IntlProvider } from '@/components/i18n/IntlProvider'
import { AuthShell } from './AuthShell'

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <IntlProvider>
      <AuthShell>{children}</AuthShell>
    </IntlProvider>
  )
}
