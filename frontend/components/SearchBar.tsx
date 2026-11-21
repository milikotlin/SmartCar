"use client";

import { useState, type FormEvent } from "react";

const PLATE_PATTERN = /^\d{7,8}$/;

/** One-click vehicles for the live demo (real registry plates; see docs/DEMO.md). */
const DEMO_PLATES = [
  { plate: "4908732", label: "Toyota" },
  { plate: "8878631", label: "Nissan" },
  { plate: "6224652", label: "High risk" },
  { plate: "19319001", label: "Anomaly" },
  { plate: "88328404", label: "EV" },
];

interface SearchBarProps {
  onSearch: (plate: string) => void;
  isLoading: boolean;
}

export function SearchBar({ onSearch, isLoading }: SearchBarProps) {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);
  const isValid = PLATE_PATTERN.test(value);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (isValid) onSearch(value);
  }

  function pick(plate: string) {
    setValue(plate);
    setTouched(false);
    onSearch(plate);
  }

  return (
    <div className="flex w-full max-w-[780px] flex-col gap-2.5">
      <form onSubmit={handleSubmit} role="search" aria-label="Vehicle lookup" className="flex flex-col gap-1.5">
        <div className="card-shadow flex h-14 items-center gap-3 rounded-xl border-2 border-line-strong bg-surface pl-5 pr-1.5 focus-within:border-accent">
          <span className="font-mono text-[12px] font-bold uppercase tracking-wider text-ink-faint">IL</span>
          <input
            type="text"
            inputMode="numeric"
            minLength={7}
            maxLength={8}
            value={value}
            onChange={(event) => setValue(event.target.value.replace(/\D/g, ""))}
            placeholder="License plate"
            aria-label="License plate, 7 or 8 digits"
            className="h-full w-full bg-transparent font-mono text-[20px] font-bold tracking-[0.14em] text-ink outline-none placeholder:font-sans placeholder:text-[16px] placeholder:font-medium placeholder:tracking-normal placeholder:text-ink-faint"
          />
          <button
            type="submit"
            disabled={isLoading}
            className="h-11 whitespace-nowrap rounded-lg bg-accent px-6 text-[15px] font-bold text-accent-ink transition-[filter] hover:brightness-110 disabled:opacity-60"
          >
            {isLoading ? "Looking up…" : "Look up"}
          </button>
        </div>
        {touched && !isValid && <span className="text-[13px] font-medium text-critical">Enter 7 or 8 digits</span>}
      </form>
      <div className="flex flex-wrap items-center gap-2" aria-label="Demo vehicles">
        <span className="text-[11.5px] font-bold uppercase tracking-wider text-ink-faint">Demo</span>
        {DEMO_PLATES.map((d) => (
          <button
            key={d.plate}
            type="button"
            onClick={() => pick(d.plate)}
            disabled={isLoading}
            data-demo-plate={d.plate}
            className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line-strong bg-surface px-3 text-[12.5px] font-semibold text-ink transition-colors hover:border-accent hover:text-accent disabled:opacity-60"
          >
            <span className="font-mono">{d.plate}</span>
            <span className="text-ink-faint">· {d.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
