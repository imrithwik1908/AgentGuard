export default function Loading() {
  return (
    <div className="space-y-4">
      <div className="h-24 animate-pulse rounded bg-slate-200" />
      <div className="grid gap-3 md:grid-cols-4">
        <div className="h-24 animate-pulse rounded bg-slate-200" />
        <div className="h-24 animate-pulse rounded bg-slate-200" />
        <div className="h-24 animate-pulse rounded bg-slate-200" />
        <div className="h-24 animate-pulse rounded bg-slate-200" />
      </div>
      <div className="h-80 animate-pulse rounded bg-slate-200" />
    </div>
  );
}
