import { RiskGauge } from "./RiskGauge";

export function RiskPanel() {
  return (
    <article className="card-shadow rounded-[14px] border border-line bg-surface p-7">
      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Predictive maintenance</p>
      <h2 className="text-xl font-semibold tracking-tight text-ink">Component risk</h2>
      <p className="mt-1 text-[13px] text-ink-soft">Two-stage ML pipeline &middot; regression + XGBoost</p>

      <div className="mt-6 grid grid-cols-3 gap-5 max-[640px]:grid-cols-1">
        <RiskGauge label="Engine" />
        <RiskGauge label="Electrical" />
        <RiskGauge label="Brakes" />
      </div>

      <p className="mt-5 border-t border-line pt-4 text-[12.5px] text-ink-soft">
        Prediction pipeline arrives in Sprint 3 &mdash; this panel is wired to render live risk scores as soon as the
        endpoint ships.
      </p>
    </article>
  );
}
