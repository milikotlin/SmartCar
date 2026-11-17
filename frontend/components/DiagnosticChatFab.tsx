export function DiagnosticChatFab() {
  return (
    <div className="fixed bottom-7 right-7 flex items-center gap-3">
      <span className="card-shadow hidden rounded-[10px] border border-line bg-surface px-3.5 py-2 text-[12.5px] text-ink-soft sm:inline">
        <strong className="font-semibold text-ink">AI Diagnostics</strong> &mdash; arriving Sprint 4
      </span>
      <button
        type="button"
        disabled
        aria-label="AI diagnostic assistant (coming soon)"
        className="card-shadow flex h-[52px] w-[52px] cursor-not-allowed items-center justify-center rounded-full bg-accent text-accent-ink opacity-90"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-[22px] w-[22px]"
        >
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
      </button>
    </div>
  );
}
