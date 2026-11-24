"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { askChat } from "@/lib/api";
import type { ChatAnswer } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  text: string;
  meta?: ChatAnswer;
}

interface Props {
  plate: string | null;
  odometerKm: number | null;
}

export function DiagnosticChatFab({ plate, odometerKm }: Props) {
  const t = useTranslations("chat");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
  }, [plate]);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !plate || busy) return;
    setDraft("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const res = await askChat(plate, text, locale, odometerKm);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, meta: res }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: t("unreachable") }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed bottom-7 end-7 z-40 flex flex-col items-end gap-3">
      {open && (
        <div className="card-shadow flex h-[480px] w-[min(380px,calc(100vw-2rem))] flex-col overflow-hidden rounded-[14px] border border-line bg-surface" role="dialog" aria-label={t("dialog")}>
          <div className="border-b border-line px-4 py-3">
            <p className="text-[14px] font-semibold text-ink">{t("title")}</p>
            <p className="text-[11.5px] text-ink-soft">
              {plate ? t("scope", { plate }) : t("noVehicle")}
            </p>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-[13px]">
            {messages.length === 0 && plate && <p className="text-ink-soft">{t("hint")}</p>}
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "text-end" : ""}>
                <p dir="auto" className={`inline-block max-w-[92%] whitespace-pre-wrap rounded-[10px] px-3 py-2 text-start ${m.role === "user" ? "bg-accent text-accent-ink" : "bg-paper text-ink"}`}>{m.text}</p>
                {m.meta && (
                  <details className="mt-1 text-[11px] text-ink-faint">
                    <summary className="cursor-pointer">{m.meta.source === "openai" ? t("generated", { model: m.meta.model ?? "" }) : t("ruleBased")}</summary>
                    <ul className="mt-1 list-disc ps-4">{m.meta.context.map((c) => <li key={c} dir="auto">{c}</li>)}</ul>
                    {m.meta.note && <p className="mt-1">{t("note", { note: m.meta.note })}</p>}
                  </details>
                )}
              </div>
            ))}
            {busy && <p className="text-ink-faint">{t("thinking")}</p>}
            <div ref={endRef} />
          </div>
          <form onSubmit={send} className="flex gap-2 border-t border-line p-3">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={!plate}
              maxLength={1000}
              placeholder={t("placeholder")}
              aria-label={t("inputLabel")}
              className="w-full rounded-md border border-line-strong bg-paper px-3 py-2 text-[13px] text-ink outline-none focus:border-accent"
            />
            <button type="submit" disabled={!plate || busy} className="rounded-md bg-accent px-3 py-2 text-[13px] font-semibold text-accent-ink disabled:opacity-60">{t("send")}</button>
          </form>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? t("close") : t("open")}
        aria-expanded={open}
        className="card-shadow flex h-[52px] w-[52px] items-center justify-center rounded-full bg-accent text-accent-ink transition-[filter] hover:brightness-110"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="h-[22px] w-[22px]">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
      </button>
    </div>
  );
}
