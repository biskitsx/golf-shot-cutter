import { getRequestConfig } from "next-intl/server";
import { notFound } from "next/navigation";

import { type Locale, locales } from "./config";

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale: Locale | undefined = locales.includes(requested as Locale)
    ? (requested as Locale)
    : undefined;
  if (!locale) notFound();
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
