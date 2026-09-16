export function EmptyState({
  title,
  description
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded border border-dashed border-slate-300 bg-white p-8 text-center">
      <h2 className="text-base font-semibold text-ink-950">{title}</h2>
      <p className="mt-2 text-sm text-slate-600">{description}</p>
    </div>
  );
}

