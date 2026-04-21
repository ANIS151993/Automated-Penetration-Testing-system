type StatusCardProps = {
  title: string;
  value: string;
  detail: string;
};

export function StatusCard({ title, value, detail }: StatusCardProps) {
  return (
    <article className="rounded-[24px] border border-white/10 bg-white/5 p-5 shadow-panel">
      <p className="text-xs uppercase tracking-[0.3em] text-white/48">{title}</p>
      <div className="mt-4 text-2xl font-semibold text-accent">{value}</div>
      <p className="mt-3 text-sm leading-7 text-white/72">{detail}</p>
    </article>
  );
}
