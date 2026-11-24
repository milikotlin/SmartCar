"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { searchCities } from "@/lib/api";
import type { City } from "@/lib/types";

interface Props {
  selected: City | null;
  onSelect: (city: City) => void;
}

/** City field: type in Hebrew or English, choose from the official localities. */
export function CityCombobox({ selected, onSelect }: Props) {
  const t = useTranslations("garages");
  const locale = useLocale();
  const listId = useId();
  const [text, setText] = useState("");
  const [options, setOptions] = useState<City[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [unknown, setUnknown] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const nameOf = (c: City) => (locale === "he" ? c.name_he : c.name_en);

  // the chosen city is shown in the language of the interface (also after the language changes)
  useEffect(() => setText(selected ? (locale === "he" ? selected.name_he : selected.name_en) : ""), [selected, locale]);

  const typed = text.trim();
  const isSelected = selected !== null && typed === nameOf(selected);
  useEffect(() => {
    setUnknown(false);
    if (typed.length < 2 || isSelected) {
      setOptions([]);
      return;
    }
    const abort = new AbortController();
    const timer = setTimeout(() => {
      searchCities(typed, abort.signal)
        .then((found) => {
          setOptions(found);
          setActive(0);
          setUnknown(found.length === 0);
        })
        .catch(() => undefined); // aborted, or the register is down: the search itself reports it
    }, 200);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [typed, isSelected]);

  useEffect(() => {
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  function choose(c: City) {
    setText(nameOf(c));
    setOpen(false);
    setOptions([]);
    onSelect(c);
  }

  async function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      if (options.length) setActive((a) => (a + (e.key === "ArrowDown" ? 1 : options.length - 1)) % options.length);
    } else if (e.key === "Escape") setOpen(false);
    else if (e.key === "Enter") {
      e.preventDefault();
      if (options.length) choose(options[active]);
      else if (isSelected && selected) onSelect(selected);
      else if (typed.length >= 2) {
        const found = await searchCities(typed).catch(() => [] as City[]); // Enter before the suggestions arrived
        if (found.length) choose(found[0]);
        else setUnknown(true);
      }
    }
  }

  const showList = open && options.length > 0;
  return (
    <div ref={box} className="relative min-w-0 flex-1">
      <label className="text-[12px] font-bold uppercase tracking-wider text-ink-faint" htmlFor={`${listId}-input`}>
        {t("cityLabel")}
      </label>
      <input
        id={`${listId}-input`}
        data-testid="garage-city"
        type="text"
        role="combobox"
        dir="auto"
        autoComplete="off"
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList ? `${listId}-${active}` : undefined}
        aria-invalid={unknown || undefined}
        value={text}
        placeholder={t("cityPlaceholder")}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={(e) => e.target.select()}
        onKeyDown={onKeyDown}
        className="mt-1 h-12 w-full rounded-lg border-2 border-line-strong bg-paper px-3 text-[15px] font-semibold text-ink outline-none placeholder:font-normal focus:border-accent ltr:text-left rtl:text-right"
      />
      {showList && (
        <ul id={listId} role="listbox" aria-label={t("citySuggestions")} className="card-shadow absolute inset-x-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-lg border border-line-strong bg-surface py-1">
          {options.map((c, i) => (
            <li
              key={c.code}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              data-city={c.code}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(c);
              }}
              className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 px-3 text-[14px] ${i === active ? "bg-chip" : ""}`}
            >
              <span className="min-w-0 truncate font-semibold text-ink">
                <bdi>{nameOf(c)}</bdi> <bdi className="text-[12.5px] font-normal text-ink-faint">{locale === "he" ? c.name_en : c.name_he}</bdi>
              </span>
              <span className="whitespace-nowrap text-[12px] text-ink-faint">{t("cityGarages", { count: c.garages })}</span>
            </li>
          ))}
        </ul>
      )}
      {unknown && (
        <p role="alert" className="mt-1 text-[13px] font-semibold text-critical" data-testid="garage-city-unknown">
          {t("cityUnknown")}
        </p>
      )}
    </div>
  );
}
