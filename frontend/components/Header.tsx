import { useTranslations } from "next-intl";
import { LanguageSwitch } from "./LanguageSwitch";
import { SearchBar } from "./SearchBar";

interface HeaderProps {
  onSearch: (plate: string) => void;
  isLoading: boolean;
}

export function Header({ onSearch, isLoading }: HeaderProps) {
  const t = useTranslations("header");
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-paper/95 backdrop-blur max-[640px]:static">
      <div className="mx-auto grid max-w-[1400px] grid-cols-[1fr_auto] items-center gap-x-6 gap-y-4 px-8 py-4 lg:grid-cols-[auto_minmax(0,1fr)_auto] max-[640px]:px-4">
        <div className="flex min-w-0 flex-col">
          <span dir="ltr" className="text-[22px] font-bold tracking-tight text-ink rtl:text-right">
            smartcar<span className="text-accent">·</span>ops
          </span>
          <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-ink-faint">{t("tagline")}</span>
        </div>
        <div className="flex flex-col items-end gap-2 lg:order-last">
          <LanguageSwitch />
          <a
            href="#garages"
            className="inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-full border border-line-strong bg-surface px-3 text-[13px] font-bold text-ink transition-colors hover:border-accent hover:text-accent"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4" aria-hidden="true">
              <path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z" />
              <circle cx="12" cy="9.5" r="2.5" />
            </svg>
            {t("garages")}
          </a>
        </div>
        <div className="col-span-2 flex lg:col-span-1 lg:justify-end">
          <SearchBar onSearch={onSearch} isLoading={isLoading} />
        </div>
      </div>
    </header>
  );
}
