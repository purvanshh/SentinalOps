import { AgentExecution } from "@/types/dashboard";

type AgentTimelineProps = {
  executions: AgentExecution[];
};

export function AgentTimeline({ executions }: AgentTimelineProps) {
  return (
    <section className="trace-card">
      <div className="eyebrow">Agent Trace</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Workflow progression
      </h3>
      <div className="trace-flow">
        {executions.map((item) => (
          <div className="trace-node" key={item.id}>
            <div className="row-top">
              <strong>{item.agent_name}</strong>
              <span className={`pill ${item.status === "completed" ? "success" : item.status.includes("approval") ? "warning" : ""}`}>
                {item.status}
              </span>
            </div>
            <div className="muted">{item.created_at}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
