import { AgentGraph } from "@/features/agents/AgentGraph";
import { AgentTimeline } from "@/features/agents/AgentTimeline";

export default function IncidentDetailPage({ params }: { params: { id: string } }) {
  return (
    <div className="grid" style={{ marginTop: 24 }}>
      <section className="list-card">
        <div className="eyebrow">Incident Detail</div>
        <h2 className="title" style={{ fontSize: "1.8rem", marginTop: 8 }}>
          Incident {params.id}
        </h2>
        <p className="muted">
          This view is prepared for agent step inspection, tool call review, and postmortem drill-down once the live API
          data path is fully wired.
        </p>
        <AgentTimeline />
      </section>
      <AgentGraph />
    </div>
  );
}
