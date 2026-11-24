"use client";

import "leaflet/dist/leaflet.css";
import type { LayerGroup, Map as LeafletMap } from "leaflet";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import type { Garage } from "@/lib/types";

interface Props {
  garages: Garage[];
  /** the user's own position (GPS search only); stays in the page */
  you: { lat: number; lon: number } | null;
  activeId: number | null;
  onSelect: (id: number) => void;
}

const placeKey = (g: Garage) => `${g.lat},${g.lon}`;

/** OpenStreetMap map of the garages whose position is known. Garages at the same address share one pin. */
export function GarageMap({ garages, you, activeId, onSelect }: Props) {
  const t = useTranslations("garages");
  const locale = useLocale();
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const layer = useRef<LayerGroup | null>(null);
  const pins = useRef(new Map<string, HTMLElement>());
  const [ready, setReady] = useState(false);
  const select = useRef(onSelect);
  useEffect(() => {
    select.current = onSelect;
  });

  useEffect(() => {
    let cancelled = false;
    void import("leaflet").then((L) => {
      if (cancelled || !node.current || map.current) return;
      const m = L.map(node.current, { scrollWheelZoom: false }).setView([31.9, 34.9], 9);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        referrerPolicy: "strict-origin-when-cross-origin", // the OpenStreetMap tile policy asks for a Referer
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
      }).addTo(m);
      layer.current = L.layerGroup().addTo(m);
      map.current = m;
      setReady(true);
    });
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    void import("leaflet").then((L) => {
      if (cancelled || !map.current || !layer.current) return;
      layer.current.clearLayers();
      pins.current.clear();
      const places = new Map<string, { index: number; garage: Garage }[]>();
      garages.forEach((garage, i) => {
        if (garage.lat === null || garage.lon === null) return;
        places.set(placeKey(garage), [...(places.get(placeKey(garage)) ?? []), { index: i + 1, garage }]);
      });
      const points: [number, number][] = [];
      const addPin = (lat: number, lon: number, text: string, title: string, className: string) => {
        const pin = document.createElement("div");
        pin.className = `garage-pin ${className}`;
        pin.textContent = text;
        points.push([lat, lon]);
        const marker = L.marker([lat, lon], { icon: L.divIcon({ html: pin, className: "", iconSize: [28, 28], iconAnchor: [14, 14] }), title, alt: title });
        marker.addTo(layer.current!);
        return { pin, marker };
      };
      for (const [key, members] of places) {
        const first = members[0];
        const several = members.length > 1;
        const { pin, marker } = addPin(
          first.garage.lat!,
          first.garage.lon!,
          several ? `${first.index}+` : String(first.index),
          several ? t("garagesHere", { count: members.length }) : first.garage.name,
          "",
        );
        pins.current.set(key, pin);
        const popup = document.createElement("div");
        popup.dir = locale === "he" ? "rtl" : "ltr";
        for (const m of members.slice(0, 6)) {
          const line = document.createElement("button"); // text only: published names are never inserted as HTML
          line.type = "button";
          line.dir = "auto";
          line.style.cssText = "display:block;width:100%;text-align:start;font-weight:600;padding:3px 0;color:#0f1216";
          line.textContent = `${m.index}. ${m.garage.name}`;
          line.onclick = () => select.current(m.garage.id);
          popup.append(line);
        }
        marker.bindPopup(popup);
        marker.on("click", () => select.current(first.garage.id));
      }
      if (you) addPin(you.lat, you.lon, "●", t("you"), "is-you");
      if (points.length) map.current.fitBounds(L.latLngBounds(points), { padding: [34, 34], maxZoom: 15 });
    });
    return () => {
      cancelled = true;
    };
  }, [ready, garages, you, locale, t]);

  // the chosen garage only restyles its pin and moves the map to it
  useEffect(() => {
    if (!ready || activeId === null) return;
    const g = garages.find((x) => x.id === activeId);
    pins.current.forEach((pin, key) => pin.classList.toggle("is-active", g !== undefined && key === placeKey(g)));
    if (g && g.lat !== null && g.lon !== null) map.current?.panTo([g.lat, g.lon]);
  }, [ready, activeId, garages]);

  const empty = !you && garages.every((g) => g.lat === null);
  return (
    <div className="garage-map relative isolate h-full w-full overflow-hidden rounded-xl border border-line" role="region" aria-label={t("map")}>
      <div ref={node} dir="ltr" className="h-full w-full" data-testid="garage-map" />
      {empty && <p className="absolute inset-x-4 top-4 z-[1000] rounded-lg bg-surface px-3 py-2 text-center text-[13px] font-semibold text-ink-soft">{t("mapNone")}</p>}
    </div>
  );
}
