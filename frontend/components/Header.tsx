import { SearchBar } from "./SearchBar";

interface HeaderProps {
  onSearch: (plate: string) => void;
  isLoading: boolean;
}

export function Header({ onSearch, isLoading }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 border-b border-line bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-4 px-8 py-4 lg:flex-row lg:items-center lg:justify-between max-[640px]:px-4">
        <div className="flex flex-col">
          <span className="text-[22px] font-bold tracking-tight text-ink">
            smartcar<span className="text-accent">·</span>ops
          </span>
          <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-ink-faint">Two-stage ML · Predictive maintenance</span>
        </div>
        <SearchBar onSearch={onSearch} isLoading={isLoading} />
      </div>
    </header>
  );
}
