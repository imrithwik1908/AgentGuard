export default function Loading() {
  return (
    <section className="mx-auto flex min-h-[58vh] max-w-2xl items-center justify-center px-6 text-center">
      <div>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 text-sm font-bold text-white shadow-panel">
          AG
        </div>
        <div className="mx-auto mt-6 h-1.5 w-40 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full w-1/2 animate-pulse rounded-full bg-cyan-600" />
        </div>
        <h1 className="mt-6 text-xl font-semibold text-slate-950">Connecting to AgentGuard</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Loading your workspace and evaluation evidence. This can take a moment after inactivity.
        </p>
      </div>
    </section>
  );
}
