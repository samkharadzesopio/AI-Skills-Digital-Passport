import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
const messages = {
 en: { overview: 'Overview', skills: 'My skills', credentials: 'Credentials', passport: 'Digital passport', gap: 'Skills gap analyzer', game: 'AI playground', profile: 'Profile & settings', welcome: 'Your next chapter starts with AI.', subtitle: 'Build your skills. Earn recognition. Show the world what you can do.', dashboard: 'My dashboard', greeting: 'Welcome back, Nino', admin: 'University admin', verify: 'Public verification' },
 ka: { overview: 'მიმოხილვა', skills: 'ჩემი უნარები', credentials: 'სერტიფიკატები', passport: 'ციფრული პასპორტი', gap: 'უნარების ანალიზი', game: 'AI სათამაშო სივრცე', profile: 'პროფილი და პარამეტრები', welcome: 'შენი ახალი ეტაპი იწყება AI-ით.', subtitle: 'განავითარე უნარები. მიიღე აღიარება. აჩვენე მსოფლიოს შენი შესაძლებლობები.', dashboard: 'ჩემი პანელი', greeting: 'კეთილი იყოს შენი დაბრუნება, ნინო', admin: 'ადმინისტრაცია', verify: 'საჯარო გადამოწმება' },
}
export type MessageKey = keyof typeof messages.en
const Context = createContext({ locale: 'en', toggle: () => {}, t: (key: MessageKey): string => messages.en[key] })
export function LocaleProvider({ children }: { children: ReactNode }) {
 const [locale, setLocale] = useState<'en' | 'ka'>(() => localStorage.getItem('btu-locale') === 'ka' ? 'ka' : 'en')
 useEffect(() => { document.documentElement.lang = locale; localStorage.setItem('btu-locale', locale) }, [locale])
 return <Context.Provider value={{ locale, toggle: () => setLocale(locale === 'en' ? 'ka' : 'en'), t: key => messages[locale][key] }}>{children}</Context.Provider>
}
// eslint-disable-next-line react-refresh/only-export-components
export const useLocale = () => useContext(Context)
