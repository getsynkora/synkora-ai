import { NextIntlClientProvider } from 'next-intl'
import { getLocale, getMessages } from 'next-intl/server'
import { HtmlLang } from './HtmlLang'

/**
 * Gives the screens below it their translations. Only the signed-in and sign-in
 * screens use it, so the public marketing pages stay statically rendered.
 */
export async function IntlProvider({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <HtmlLang locale={locale} />
      {children}
    </NextIntlClientProvider>
  )
}
