export default function Loading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12 space-y-6 animate-pulse">
      <div className="h-6 w-32 rounded bg-[color:var(--surface-raised)]" />
      <div className="h-28 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--line)]" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-72 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--line)]" />
        <div className="lg:col-span-1 h-72 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--line)]" />
      </div>
      <div className="h-56 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--line)]" />
    </div>
  );
}
