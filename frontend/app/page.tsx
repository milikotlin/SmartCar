"use client";

import { useCallback, useRef, useState } from "react";
import { DiagnosticChatFab } from "@/components/DiagnosticChatFab";
import { Header } from "@/components/Header";
import { MaintenanceHistory } from "@/components/MaintenanceHistory";
import { MaintenancePanel } from "@/components/MaintenancePanel";
import { MlMetricsDrawer } from "@/components/MlMetricsDrawer";
import { FailureRiskPanel } from "@/components/FailureRiskPanel";
import { RecallsPanel } from "@/components/RecallsPanel";
import { RiskPanel } from "@/components/RiskPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { VehicleSpecCard } from "@/components/VehicleSpecCard";
import { ApiError, fetchInspections, fetchMaintenance, fetchPrediction, InvalidPlateError, VehicleNotFoundError } from "@/lib/api";
import type { MileageMode } from "@/lib/mileage";
import type { InspectionRecord, MaintenanceRecord, Prediction } from "@/lib/types";

type DashboardState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; prediction: Prediction; maintenance: MaintenanceRecord[]; inspections: InspectionRecord[] };

export default function DashboardPage() {
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
      const [prediction, maintenance, inspections] = await Promise.all([fetchPrediction(p, odo), fetchMaintenance(p), fetchInspections(p)]);
      if (id !== requestId.current) return;
      setState({ status: "success", prediction, maintenance, inspections });
    } catch (error) {
      if (id !== requestId.current) return;
      const message =
        error instanceof VehicleNotFoundError || error instanceof InvalidPlateError || error instanceof ApiError
          ? error.message
          : "Something went wrong while reaching the backend. Is it running?";
      setState({ status: "error", message });
    } finally {
      clearTimeout(slowTimer);
      if (id === requestId.current) {
        setRefreshing(false);
        setSlowRefresh(false);
      }
    }
  }, []);

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
            {state.message}
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
              Model 1 v{state.prediction.provenance.model1_version} · Model 2 v{state.prediction.provenance.model2_version} · UK MOT comparison v1
            </p>
          </>
        )}
      </main>

      <DiagnosticChatFab plate={state.status === "success" ? plate : null} odometerKm={reportedKm} />
    </>
  );
}

function EmptyState() {
  const steps = [
    ["1", "Registry", "Live data.gov.il profile"],
    ["2", "Model 1", "XGBoost mileage imputation"],
    ["3", "Model 2", "Failure-risk classifier"],
    ["4", "Rules & recalls", "Maintenance + official data"],
  ];
  return (
    <div className="flex flex-col items-center gap-6 rounded-2xl border-2 border-dashed border-line-strong px-6 py-16 text-center">
      <p className="text-[24px] font-bold tracking-tight text-ink">Look up a vehicle</p>
      <div className="grid w-full max-w-[880px] grid-cols-4 gap-3 max-[760px]:grid-cols-2">
        {steps.map(([n, title, sub]) => (
          <div key={n} className="rounded-xl border border-line bg-surface p-4 text-left">
            <span className="font-mono text-[13px] font-bold text-accent">{n}</span>
            <p className="mt-1 text-[15px] font-bold text-ink">{title}</p>
            <p className="text-[12.5px] text-ink-soft">{sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
