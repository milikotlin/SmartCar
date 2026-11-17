"use client";

import { useState } from "react";
import { DiagnosticChatFab } from "@/components/DiagnosticChatFab";
import { Header } from "@/components/Header";
import { MaintenanceHistory } from "@/components/MaintenanceHistory";
import { RiskPanel } from "@/components/RiskPanel";
import { Skeleton } from "@/components/ui/Skeleton";
import { VehicleSpecCard } from "@/components/VehicleSpecCard";
import { fetchVehicleProfile, VehicleNotFoundError } from "@/lib/api";
import type { VehicleProfile } from "@/lib/types";

type DashboardState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; vehicle: VehicleProfile };

export default function DashboardPage() {
  const [state, setState] = useState<DashboardState>({ status: "idle" });

  async function handleSearch(plate: string) {
    setState({ status: "loading" });
    try {
      const vehicle = await fetchVehicleProfile(plate);
      setState({ status: "success", vehicle });
    } catch (error) {
      const message =
        error instanceof VehicleNotFoundError
          ? error.message
          : "Something went wrong while reaching the backend. Is it running?";
      setState({ status: "error", message });
    }
  }

  return (
    <>
      <Header onSearch={handleSearch} isLoading={state.status === "loading"} />

      <main className="mx-auto flex max-w-[1180px] flex-col gap-10 px-8 pb-24 pt-10">
        {state.status === "idle" && <EmptyState />}

        {state.status === "error" && (
          <p className="rounded-[10px] border border-critical bg-critical-bg px-5 py-4 text-sm text-critical">
            {state.message}
          </p>
        )}

        {state.status === "loading" && (
          <div className="grid grid-cols-[minmax(280px,380px)_1fr] gap-7 max-[880px]:grid-cols-1">
            <Skeleton className="h-[320px]" />
            <Skeleton className="h-[320px]" />
          </div>
        )}

        {state.status === "success" && (
          <>
            <div className="grid grid-cols-[minmax(280px,380px)_1fr] items-stretch gap-7 max-[880px]:grid-cols-1">
              <VehicleSpecCard vehicle={state.vehicle} />
              <RiskPanel />
            </div>
            <MaintenanceHistory />
          </>
        )}
      </main>

      <DiagnosticChatFab />
    </>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-[14px] border border-dashed border-line py-24 text-center">
      <p className="text-base font-medium text-ink">Look up a vehicle to get started</p>
      <p className="max-w-sm text-sm text-ink-soft">
        Enter a 7 or 8-digit Israeli license plate above to pull a live profile from the Ministry of Transport registry.
      </p>
    </div>
  );
}
