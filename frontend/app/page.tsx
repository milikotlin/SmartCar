"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { DiagnosticChatFab } from "@/components/DiagnosticChatFab";
import { GaragesPanel } from "@/components/garages/GaragesPanel";
import { Header } from "@/components/Header";
import { MaintenanceHistory } from "@/components/MaintenanceHistory";
import { MaintenancePanel } from "@/components/MaintenancePanel";
import { MlMetricsDrawer } from "@/components/MlMetricsDrawer";
import { FailureRiskPanel } from "@/components/FailureRiskPanel";
import { RecallsPanel } from "@/components/RecallsPanel";
import { RiskPanel } from "@/components/RiskPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { VehicleSpecCard } from "@/components/VehicleSpecCard";
import { errorCode, fetchInspections, fetchMaintenance, fetchPrediction, type ErrorCode } from "@/lib/api";
import type { Locale } from "@/i18n/config";
import type { MileageMode } from "@/lib/mileage";
import type { InspectionRecord, MaintenanceRecord, Prediction } from "@/lib/types";

type DashboardState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; code: ErrorCode }
  | { status: "success"; lang: Locale; prediction: Prediction; maintenance: MaintenanceRecord[]; inspections: InspectionRecord[] };

export default function DashboardPage() {
  const t = useTranslations();
  const locale = useLocale();
  const [state, setState] = useState<DashboardState>({ status: "idle" });
  const [plate, setPlate] = useState<string | null>(null);
  // Mileage choice: "estimate" (Model 1, the default) or "reported" (a value typed by the user). The typed value lives only in this page state: it is sent with each request and never stored.
  const [mileageMode, setMileageMode] = useState<MileageMode>("estimate");
  const [reportedKm, setReportedKm] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [slowRefresh, setSlowRefresh] = useState(false); // a refresh that takes long: the old risk panel is replaced by a placeholder instead of staying on screen
  const requestId = useRef(0); // only the answer to the LAST request may reach the screen (the user can switch options while a request is running)
  const requestedKm = useRef<number | null>(null); // the mileage the last request was sent with

  const load = useCallback(async (p: string, odo: number | null, quiet = false) => {
    const id = ++requestId.current;
    requestedKm.current = odo;
    let slowTimer: ReturnType<typeof setTimeout> | undefined;
    if (quiet) {
      setRefreshing(true);
      slowTimer = setTimeout(() => id === requestId.current && setSlowRefresh(true), 250);
    } else setState({ status: "loading" });
    try {
      const [prediction, maintenance, inspections] = await Promise.all([fetchPrediction(p, locale, odo), fetchMaintenance(p), fetchInspections(p)]);
      if (id !== requestId.current) return;
      setState({ status: "success", lang: locale, prediction, maintenance, inspections });
    } catch (error) {
      if (id !== requestId.current) return;
      setState({ status: "error", code: errorCode(error) });
    } finally {
      clearTimeout(slowTimer);
      if (id === requestId.current) {
        setRefreshing(false);
        setSlowRefresh(false);
      }
    }
  }, [locale]);

  // another language: the same vehicle is read again in it (same inputs, same predictions, other texts); the typed mileage and the chosen option stay
  useEffect(() => {
    if (plate && state.status === "success" && state.lang !== locale) void load(plate, requestedKm.current, true);
  }, [locale, plate, state, load]);

  async function handleSearch(p: string) {
    setPlate(p);
    setMileageMode("estimate");
    setReportedKm(null);
    await load(p, null);
  }

  function handleModeChange(mode: MileageMode) {
    setMileageMode(mode);
    if (mode === "estimate") {
      // back to the automatic estimate: drop the typed value and reload so that no result computed from it stays on screen
      setReportedKm(null);
      if (plate && requestedKm.current !== null) void load(plate, null, true);
    }
  }

  function handleApply(km: number) {
    setReportedKm(km);
    if (plate) void load(plate, km, true);
  }

  return (
    <>
      <Header onSearch={handleSearch} isLoading={state.status === "loading"} />

      <main className="mx-auto flex max-w-[1400px] flex-col gap-6 px-8 pb-28 pt-6 max-[640px]:px-4">
        {state.status === "idle" && <EmptyState />}

        {state.status === "error" && (
          <p role="alert" className="rounded-xl border-2 border-critical bg-critical-bg px-5 py-4 text-[15px] font-semibold text-critical">
            {t(`errors.${state.code}`)}
          </p>
        )}

        {state.status === "loading" && (
          <div className="grid grid-cols-[420px_1fr] gap-6 max-[1024px]:grid-cols-1">
            <Skeleton className="h-[640px]" />
            <div className="flex flex-col gap-6">
              <Skeleton className="h-[230px]" />
              <Skeleton className="h-[300px]" />
            </div>
          </div>
        )}

        {state.status === "success" && (
          <>
            <div className="grid grid-cols-[420px_1fr] items-start gap-6 max-[1024px]:grid-cols-1">
              <VehicleSpecCard
                vehicle={state.prediction.vehicle}
                mileage={state.prediction.mileage}
                mode={mileageMode}
                onModeChange={handleModeChange}
                onApply={handleApply}
                refreshing={refreshing}
                model2KmSource={state.prediction.failure_risk ? String(state.prediction.failure_risk.inputs.km_source ?? "") : undefined}
              />
              <div className={`flex flex-col gap-6 ${refreshing ? "pointer-events-none opacity-50" : ""}`} aria-busy={refreshing}>
                {slowRefresh ? (
                  <>
                    <Skeleton className="h-[230px]" />
                    <Skeleton className="h-[300px]" />
                  </>
                ) : (
                  <>
                    {state.prediction.failure_risk && <FailureRiskPanel risk={state.prediction.failure_risk} />}
                    <RiskPanel risk={state.prediction.inspection_risk} />
                    <MlMetricsDrawer failure={state.prediction.failure_risk} inspection={state.prediction.inspection_risk} />
                  </>
                )}
              </div>
            </div>

            <div className={`grid grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] items-start gap-6 max-[1024px]:grid-cols-1 ${refreshing ? "pointer-events-none opacity-50" : ""}`} aria-busy={refreshing}>
              <MaintenancePanel info={state.prediction.maintenance} />
              <div className="flex flex-col gap-6">
                <RecallsPanel info={state.prediction.recalls} />
                <MaintenanceHistory
                  plate={state.prediction.vehicle.license_plate}
                  maintenance={state.maintenance}
                  inspections={state.inspections}
                  history={state.prediction.history}
                  lastTestDate={state.prediction.vehicle.last_test_date}
                  onChanged={() => plate && load(plate, reportedKm, true)}
                />
              </div>
            </div>

            <p className="text-center font-mono text-[11.5px] text-ink-faint">
              {t("footer.versions", { model1: state.prediction.provenance.model1_version, model2: state.prediction.provenance.model2_version })}
            </p>
          </>
        )}

        <GaragesPanel electrified={state.status === "success" && ["electric", "hybrid"].includes(String(state.prediction.mileage.model_inputs.fuel))} />
      </main>

      <DiagnosticChatFab plate={state.status === "success" ? plate : null} odometerKm={reportedKm} />
    </>
  );
}

function EmptyState() {
  const t = useTranslations("empty");
  const steps = ["registry", "model1", "model2", "rules"] as const;
  return (
    <div className="flex flex-col items-center gap-6 rounded-2xl border-2 border-dashed border-line-strong px-6 py-16 text-center">
      <p className="text-[24px] font-bold tracking-tight text-ink">{t("title")}</p>
      <div className="grid w-full max-w-[880px] grid-cols-4 gap-3 max-[760px]:grid-cols-2">
        {steps.map((step, i) => (
          <div key={step} className="rounded-xl border border-line bg-surface p-4 text-start">
            <span className="font-mono text-[13px] font-bold text-accent">{i + 1}</span>
            <p className="mt-1 text-[15px] font-bold text-ink">{t(`steps.${step}.title`)}</p>
            <p className="text-[12.5px] text-ink-soft">{t(`steps.${step}.text`)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
