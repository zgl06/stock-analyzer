export default function Loading() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12 space-y-6 animate-pulse">
      <div className="h-6 w-32 bg-slate-200 dark:bg-slate-800 rounded" />
      <div className="h-24 bg-slate-200 dark:bg-slate-800 rounded-lg" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-64 bg-slate-200 dark:bg-slate-800 rounded-lg" />
        <div className="lg:col-span-1 h-64 bg-slate-200 dark:bg-slate-800 rounded-lg" />
      </div>
      <div className="h-48 bg-slate-200 dark:bg-slate-800 rounded-lg" />
    </div>
  );
}
