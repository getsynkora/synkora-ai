import { IntlProvider } from '@/components/i18n/IntlProvider'

export default function ShareLayout({ children }: { children: React.ReactNode }) {
  return <IntlProvider>{children}</IntlProvider>
}
