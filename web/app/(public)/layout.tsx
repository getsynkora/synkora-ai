import { IntlProvider } from '@/components/i18n/IntlProvider'

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <IntlProvider>{children}</IntlProvider>
}
