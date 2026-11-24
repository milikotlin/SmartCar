"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition, type ReactNode } from "react";
import { LOCALE_COOKIE, LOCALES, type Locale } from "@/i18n/config";

// Drawn flags: Windows browsers do not draw the flag emoji.
const FLAG: Record<Locale, ReactNode> = {
  en: (
    <svg viewBox="0 0 60 40" className="h-3.5 w-5 rounded-[2px]" aria-hidden="true">
      <path fill="#012169" d="M0 0h60v40H0z" />
      <path stroke="#fff" strokeWidth="8" d="m0 0 60 40M60 0 0 40" />
      <path stroke="#C8102E" strokeWidth="4" d="m0 0 60 40M60 0 0 40" />
      <path stroke="#fff" strokeWidth="13" d="M30 0v40M0 20h60" />
      <path stroke="#C8102E" strokeWidth="8" d="M30 0v40M0 20h60" />
    </svg>
  ),
  he: (
    <svg viewBox="0 0 60 40" className="h-3.5 w-5 rounded-[2px]" aria-hidden="true">
      <path fill="#fff" d="M0 0h60v40H0z" />
      <path fill="#0038B8" d="M0 4h60v6H0zM0 30h60v6H0z" />
      <path fill="none" stroke="#0038B8" strokeWidth="1.8" d="m30 13 6 10.5H24zM30 27l-6-10.5h12z" />
    </svg>
  ),
};

export function LanguageSwitch() {
  const t = useTranslations("language");
  const locale = useLocale();
  const router = useRouter();
  const [pending, start] = useTransition();

  function choose(next: Locale) {
    if (next === locale) return;
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    start(() => router.refresh()); // the page keeps its state (vehicle, typed mileage, chat): only the language changes
  }

  return (
    <div role="group" aria-label={t("label")} aria-busy={pending} className="inline-flex rounded-lg bg-chip p-1">
      {LOCALES.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={l === locale}
          data-locale={l}
          onClick={() => choose(l)}
          className={`inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 text-[13px] font-bold transition-colors ${l === locale ? "bg-surface text-ink shadow-sm" : "text-ink-soft hover:text-ink"}`}
        >
          {FLAG[l]}
          {t(l)}
        </button>
      ))}
    </div>
  );
}
