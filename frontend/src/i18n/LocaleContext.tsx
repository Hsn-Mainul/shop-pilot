import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { messages, type Locale, type MessageKey } from './messages'

interface LocaleState {
  locale: Locale
  setLocale: (l: Locale) => void
  t: (key: MessageKey) => string
}

const LocaleContext = createContext<LocaleState | null>(null)

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    const saved = localStorage.getItem('shop_locale')
    return saved === 'bn' ? 'bn' : 'en'
  })

  const value = useMemo<LocaleState>(
    () => ({
      locale,
      setLocale: (l) => {
        localStorage.setItem('shop_locale', l)
        setLocale(l)
      },
      t: (key) => messages[locale][key] ?? messages.en[key],
    }),
    [locale],
  )

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
}

export function useLocale() {
  const ctx = useContext(LocaleContext)
  if (!ctx) throw new Error('useLocale must be used within LocaleProvider')
  return ctx
}
