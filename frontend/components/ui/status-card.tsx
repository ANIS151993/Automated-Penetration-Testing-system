type StatusCardProps = {
  title: string;
  value: string;
  detail: string;
};

export function StatusCard({ title, value, detail }: StatusCardProps) {
  return (
    <article className="border border-border-subtle bg-surface-secondary p-4">
      <p className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary">{title}</p>
      <div className="mt-3 font-display text-[22px] font-bold text-secondary">{value}</div>
      <p className="mt-2 font-mono text-[11px] leading-relaxed text-text-secondary">{detail}</p>
    </article>
  );
}
