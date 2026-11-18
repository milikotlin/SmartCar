"use client";

import { useCallback, useState } from "react";
import { DiagnosticChatFab } from "@/components/DiagnosticChatFab";
import { Header } from "@/components/Header";
import { MaintenanceHistory } from "@/components/MaintenanceHistory";
import { MaintenancePanel } from "@/components/MaintenancePanel";
import { RecallsPanel } from "@/components/RecallsPanel";
import { RiskPanel } from "@/components/RiskPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { VehicleSpecCard } from "@/components/VehicleSpecCard";
import { ApiError, fetchInspections, fetchMaintenance, fetchPrediction, InvalidPlateError, VehicleNotFoundError } from "@/lib/api";
import type { InspectionRecord, MaintenanceRecord, Prediction } from "@/lib/types";

type DashboardState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; prediction: Prediction; maintenance: MaintenanceRecord[]; inspections: InspectionRecord[] };

export default function DashboardPage() {
  const [state, setState] = useState<DashboardState>({ status: "idle" });
  const [plate, setPlate] = useState<string | null>(null);
  const [odometer, setOdometer] = useState<number | null>(null);
  const [odometerDraft, setOdometerDraft] = useState("");

  const load = useCallback(async (p: string, odo: number | null, quiet = false) => {
    if (!quiet) setState({ status: "loading" });
    try {
      const [prediction, maintenance, inspections] = await Promise.all([fetchPrediction(p, odo), fetchMaintenance(p), fetchInspections(p)]);
      setState({ status: "success", prediction, maintenance, inspections });
    } catch (error) {
      const message =
        error instanceof VehicleNotFoundError || error instanceof InvalidPlateError || error instanceof ApiError
          ? error.message
          : "Something went wrong while reaching the backend. Is it running?";
      setState({ status: "error", message });
    }
  }, []);

  async function handleSearch(p: string) {
    setPlate(p);
    setOdometer(null);
    setOdometerDraft("");
    await load(p, null);
  }

  function applyOdometer(e: React.FormEvent) {
    e.preventDefault();
    const value = odometerDraft ? Number(odometerDraft) : null;
    setOdometer(value);
    if (plate) void load(plate, value, true);
  }

  return (
    <>
      <Header onSearch={handleSearch} isLoading={state.status === "loading"} />

      <main className="mx-auto flex max-w-[1180px] flex-col gap-8 px-8 pb-28 pt-10 max-[640px]:px-4">
        {state.status === "idle" && <EmptyState />}

        {state.status === "error" && (
          <p role="alert" className="rounded-[10px] border border-critical bg-critical-bg px-5 py-4 text-sm text-critical">
            {state.message}
          </p>
        )}

        {state.status === "loading" && (
          <div className="grid grid-cols-[minmax(280px,380px)_1fr] gap-7 max-[880px]:grid-cols-1">
            <Skeleton className="h-[420px]" />
            <Skeleton className="h-[420px]" />
          </div>
        )}

        {state.status === "success" && (
          <>
            <div className="grid grid-cols-[minmax(280px,380px)_1fr] items-stretch gap-7 max-[880px]:grid-cols-1">
              <VehicleSpecCard vehicle={state.prediction.vehicle} mileage={state.prediction.mileage} />
              <div className="flex flex-col gap-4">
                <RiskPanel risk={state.prediction.inspection_risk} />
                <form onSubmit={applyOdometer} className="card-shadow flex flex-wrap items-end gap-3 rounded-[14px] border border-line bg-surface px-5 py-4">
                  <label className="min-w-[220px] flex-1 text-[12px] text-ink-soft">
                    Measured odometer (km), if known
                    <input
                      type="number"
                      min={0}
                      max={1500000}
                      value={odometerDraft}
                      onChange={(e) => setOdometerDraft(e.target.value)}
                      placeholder="Replaces the estimate and is used by the model"
                      className="mt-1 w-full rounded-md border border-line-strong bg-paper px-2.5 py-2 text-[13px] text-ink outline-none focus:border-accent"
                    />
                  </label>
                  <button type="submit" className="rounded-md border border-accent px-4 py-2 text-[13px] font-semibold text-accent">
                    {odometer ? "Update" : "Use this value"}
                  </button>
                  <p className="basis-full text-[11.5px] text-ink-faint">A measured value is never invented: without it the system shows the Model 1 estimate with its range.</p>
                </form>
              </div>
            </div>

            <div className="grid grid-cols-2 items-start gap-7 max-[1000px]:grid-cols-1">
              <MaintenancePanel info={state.prediction.maintenance} />
              <RecallsPanel info={state.prediction.recalls} />
            </div>

            <MaintenanceHistory
              plate={state.prediction.vehicle.license_plate}
              maintenance={state.maintenance}
              inspections={state.inspections}
              history={state.prediction.history}
              lastTestDate={state.prediction.vehicle.last_test_date}
              onChanged={() => plate && load(plate, odometer, true)}
            />

            <p className="text-center text-[11.5px] text-ink-faint">
              Models {state.prediction.provenance.model1_version} / {state.prediction.provenance.model2_version}. {state.prediction.provenance.notes.join(" ")}
            </p>
          </>
        )}
      </main>

      <DiagnosticChatFab plate={state.status === "success" ? plate : null} odometerKm={odometer} />
    </>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-[14px] border border-dashed border-line py-24 text-center">
      <p className="text-base font-medium text-ink">Look up a vehicle to get started</p>
      <p className="max-w-sm text-sm text-ink-soft">
        Enter a 7 or 8-digit Israeli license plate above to pull a live profile from the Ministry of Transport registry, with an estimated mileage, the estimated
        inspection-defect risk, recommended maintenance and official recalls.
      </p>
    </div>
  );
}
