import { getRequestConfig } from 'next-intl/server'
import { cookies, headers } from 'next/headers'
import { LOCALE_COOKIE, resolveLocale } from './config'

export default getRequestConfig(async () => {
  const locale = resolveLocale({
    cookie: (await cookies()).get(LOCALE_COOKIE)?.value,
    acceptLanguage: (await headers()).get('accept-language'),
  })

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  }
})
