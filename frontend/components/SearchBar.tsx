"use client";

import { useState, type FormEvent } from "react";

const PLATE_PATTERN = /^\d{7,8}$/;

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
    if (isValid) {
      onSearch(value);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      role="search"
      aria-label="Vehicle lookup"
      className="flex w-full max-w-[420px] flex-col gap-1.5"
    >
      <div className="card-shadow flex items-center gap-2.5 rounded-[10px] border border-line-strong bg-surface py-1.5 pl-4 pr-1.5">
        <input
          type="text"
          inputMode="numeric"
          minLength={7}
          maxLength={8}
          value={value}
          onChange={(event) => setValue(event.target.value.replace(/\D/g, ""))}
          placeholder="e.g. 42068203"
          aria-label="License plate, 7 or 8 digits"
          className="w-full bg-transparent font-mono text-sm tracking-wide text-ink outline-none placeholder:font-sans placeholder:text-ink-faint"
        />
        <button
          type="submit"
          disabled={isLoading}
          className="whitespace-nowrap rounded-[7px] bg-accent px-4 py-2.5 text-[13px] font-semibold text-accent-ink transition-[filter] hover:brightness-110 disabled:opacity-60"
        >
          {isLoading ? "Looking up…" : "Look up"}
        </button>
      </div>
      {touched && !isValid && <span className="text-[12px] text-critical">Enter 7 or 8 digits.</span>}
    </form>
  );
}
