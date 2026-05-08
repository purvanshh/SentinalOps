const demoTimeline = [
  { name: "Router Agent", note: "Classified as deployment regression.", status: "completed" },
  { name: "Metrics Agent", note: "Observed latency and CPU spikes.", status: "completed" },
  { name: "Logs Agent", note: "Detected SQL timeout signatures.", status: "completed" },
  { name: "Deployment Agent", note: "Correlated failure with DEP-4351.", status: "completed" },
  { name: "Root Cause Agent", note: "Ranked deployment regression highest.", status: "completed" },
  { name: "Risk Agent", note: "Recommended rollback as safer than restart.", status: "completed" },
  { name: "Approval Node", note: "Paused execution for operator review.", status: "waiting" }
];

export function AgentTimeline() {
  return (
    <section className="trace-card">
      <div className="eyebrow">Agent Trace</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Workflow progression
      </h3>
      <div className="trace-flow">
        {demoTimeline.map((item) => (
          <div className="trace-node" key={item.name}>
            <div className="row-top">
              <strong>{item.name}</strong>
              <span className={`pill ${item.status === "completed" ? "success" : "warning"}`}>
                {item.status}
              </span>
            </div>
            <div className="muted">{item.note}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
