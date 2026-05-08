type StatCardProps = {
  eyebrow: string;
  value: string;
  description: string;
};

export function StatCard({ eyebrow, value, description }: StatCardProps) {
  return (
    <article className="stat-card">
      <div className="eyebrow">{eyebrow}</div>
      <div className="stat-value">{value}</div>
      <p className="muted">{description}</p>
    </article>
  );
}
