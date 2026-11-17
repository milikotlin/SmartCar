const COLUMNS = ["Date", "Mileage", "Description", "Category", "Cost"];

export function MaintenanceHistory() {
  return (
    <section className="card-shadow rounded-[14px] border border-line bg-surface py-2">
      <div className="px-7 pt-6">
        <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wider text-ink-faint">Service log</p>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Maintenance history</h2>
        <p className="mt-1 text-[13px] text-ink-soft">Synced from PostgreSQL</p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {COLUMNS.map((column) => (
                <th
                  key={column}
                  className="border-b border-line px-7 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={COLUMNS.length} className="px-7 py-10 text-center text-[13.5px] text-ink-soft">
                No maintenance records endpoint yet &mdash; this table renders live PostgreSQL data once the Sprint 3
                history route ships.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
