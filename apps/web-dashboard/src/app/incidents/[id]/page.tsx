import { AgentGraph } from "@/features/agents/AgentGraph";
import { AgentTimeline } from "@/features/agents/AgentTimeline";
import { IncidentStream } from "@/features/incidents/IncidentStream";
import { getGraphState, getIncident } from "@/services/apiClient";

export default async function IncidentDetailPage({ params }: { params: { id: string } }) {
  const [incident, graph] = await Promise.all([
    getIncident(params.id),
    getGraphState(params.id)
  ]);

  return (
    <div className="grid" style={{ marginTop: 24 }}>
      <section className="list-card">
        <div className="eyebrow">Incident Detail</div>
        <h2 className="title" style={{ fontSize: "1.8rem", marginTop: 8 }}>
          {incident.title}
        </h2>
        <p className="muted">{incident.summary}</p>
        <div className="muted" style={{ marginTop: 8 }}>
          Severity: {incident.severity} · Status: {incident.status} · Type: {incident.incident_type ?? "unknown"}
        </div>
        <AgentTimeline executions={incident.agent_executions ?? []} />
      </section>
      <div className="stack">
        <AgentGraph graph={graph} />
        <IncidentStream incidentId={params.id} />
      </div>
    </div>
  );
}
