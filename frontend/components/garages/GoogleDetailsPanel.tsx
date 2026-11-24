"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ApiError, fetchGoogleDetails } from "@/lib/api";
import { useFmt } from "@/lib/format";
import type { Garage, GoogleDetails } from "@/lib/types";

type State = { status: "loading" } | { status: "error"; limit: boolean } | { status: "ok"; details: GoogleDetails };

/** Rating, phone and hours of one garage from Google (only with a server key). Replaces the OpenStreetMap map while it is open, so Google content is never next to another map. Nothing is stored. */
export function GoogleDetailsPanel({ garage, onClose }: { garage: Garage; onClose: () => void }) {
  const t = useTranslations("garages");
  const locale = useLocale();
  const { num } = useFmt();
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let current = true;
    setState({ status: "loading" });
    fetchGoogleDetails(garage.id, locale)
      .then((details) => current && setState({ status: "ok", details }))
      .catch((e) => current && setState({ status: "error", limit: e instanceof ApiError && e.status === 429 }));
    return () => {
      current = false;
    };
  }, [garage.id, locale]);

  const d = state.status === "ok" ? state.details : null;
  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto rounded-xl border border-line bg-paper p-5" data-testid="google-details">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[12px] font-bold uppercase tracking-wider text-ink-faint">{t("ratingTitle")}</p>
        <button type="button" onClick={onClose} className="min-h-10 rounded-lg border border-line-strong px-3 text-[13px] font-bold text-ink hover:border-accent hover:text-accent">
          {t("back")}
        </button>
      </div>
      <bdi lang="he" className="text-[18px] font-bold text-ink">
        {d?.name ?? garage.name}
      </bdi>
      {state.status === "loading" && (
        <p role="status" className="text-[14px] text-ink-soft">
          {t("ratingLoading")}
        </p>
      )}
      {state.status === "error" && (
        <p role="alert" className="text-[14px] font-semibold text-critical">
          {state.limit ? t("ratingLimit") : t("ratingError")}
        </p>
      )}
      {d && !d.matched && <p className="text-[14px] text-ink-soft">{t("ratingNone")}</p>}
      {d?.matched && (
        <>
          <p className="flex items-baseline gap-2">
            <span className="font-mono text-[30px] font-bold text-ink">{d.rating !== null ? `★ ${num(d.rating, 1)}` : t("noRating")}</span>
            {d.rating_count !== null && <span className="text-[13px] text-ink-soft">{t("ratingCount", { count: d.rating_count })}</span>}
          </p>
          {d.address && (
            <p dir="auto" className="text-[13.5px] text-ink-soft">
              {d.address}
            </p>
          )}
          {d.phone && (
            <p className="font-mono text-[14px] text-ink">
              <bdi dir="ltr">{d.phone}</bdi>
            </p>
          )}
          {d.opening_hours.length > 0 && (
            <div>
              <p className="text-[12px] font-bold uppercase tracking-wider text-ink-faint">{t("hours")}</p>
              <ul className="mt-1 text-[13.5px] text-ink">
                {d.opening_hours.map((h) => (
                  <li key={h} dir="auto">
                    {h}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.url && (
            <a href={d.url} target="_blank" rel="noopener noreferrer" className="text-[13.5px] font-bold text-accent underline">
              {t("openGoogle")}
            </a>
          )}
        </>
      )}
      {d?.attribution && <p className="mt-auto text-[12px] text-ink-faint">{d.attribution}</p>}
    </div>
  );
}
