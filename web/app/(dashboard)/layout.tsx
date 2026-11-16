import { IntlProvider } from '@/components/i18n/IntlProvider'
import { DashboardShell } from './DashboardShell'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <IntlProvider>
      <DashboardShell>{children}</DashboardShell>
    </IntlProvider>
  )
}
