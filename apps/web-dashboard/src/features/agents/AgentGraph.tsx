export function AgentGraph() {
  return (
    <section className="trace-card">
      <div className="eyebrow">Graph View</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Graph snapshot
      </h3>
      <p className="muted">
        Router → fan-out(metrics/logs/deployment) → root cause → risk → remediation → approval → execution → postmortem
      </p>
    </section>
  );
}
