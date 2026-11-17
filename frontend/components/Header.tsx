import { SearchBar } from "./SearchBar";

interface HeaderProps {
  onSearch: (plate: string) => void;
  isLoading: boolean;
}

export function Header({ onSearch, isLoading }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 overflow-hidden border-b border-line bg-paper">
      <div className="relative mx-auto flex max-w-[1180px] flex-col gap-4 px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-8">
        <div className="flex flex-shrink-0 items-baseline gap-2.5">
          <span className="text-lg font-bold tracking-tight text-ink">
            smartcar<span className="text-accent">&middot;</span>ops
          </span>
          <span className="text-xs uppercase tracking-wide text-ink-faint">Fleet Diagnostics</span>
        </div>

        <SearchBar onSearch={onSearch} isLoading={isLoading} />

        <svg
          className="pointer-events-none absolute right-[-10px] top-1/2 hidden w-[230px] -translate-y-1/2 text-ink opacity-[0.06] min-[881px]:block"
          viewBox="0 0 240 90"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M18 58 C18 44, 30 40, 42 40 L58 40 C64 28, 76 20, 92 20 L150 20 C168 20, 182 30, 190 40 L214 40 C224 40, 230 46, 230 56 L230 62 C230 66, 226 68, 222 68 L20 68 C18 68, 18 65, 18 62 Z"
            stroke="currentColor"
            strokeWidth="2.5"
          />
          <circle cx="62" cy="68" r="12" stroke="currentColor" strokeWidth="2.5" />
          <circle cx="186" cy="68" r="12" stroke="currentColor" strokeWidth="2.5" />
          <line x1="92" y1="40" x2="98" y2="22" stroke="currentColor" strokeWidth="2.5" />
          <line x1="150" y1="40" x2="146" y2="22" stroke="currentColor" strokeWidth="2.5" />
        </svg>
      </div>
    </header>
  );
}
