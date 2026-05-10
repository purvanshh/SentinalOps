import { StatCard } from "@/components/StatCard";
import { PendingApprovals } from "@/features/approvals/PendingApprovals";
import { AgentTimeline } from "@/features/agents/AgentTimeline";
import { EvaluationCharts } from "@/features/evaluations/EvaluationCharts";
import { IncidentList } from "@/features/incidents/IncidentList";
import { getIncident } from "@/services/apiClient";
import { getDashboardData } from "@/hooks/useDashboardData";

export default async function HomePage() {
  const data = await getDashboardData();
  const latestIncident = data.incidents[0] ? await getIncident(data.incidents[0].id) : null;

  return (
    <>
      <section className="hero-grid" style={{ marginTop: 24 }}>
        <StatCard eyebrow="Tracked Incidents" value={`${data.incidents.length}`} description="Incidents visible to the command center right now." />
        <StatCard eyebrow="Pending Approvals" value={`${data.approvals.length}`} description="High-risk remediation steps waiting on an operator." />
        <StatCard eyebrow="Eval Coverage" value={`${data.evaluation.count}`} description="Synthetic scenarios included in the latest summary run." />
        <StatCard eyebrow="Safety Score" value={`${Math.round(data.evaluation.summary.safety_score * 100)}%`} description="Current safety pass rate from the evaluation harness." />
      </section>
      <div className="grid">
        <div className="stack">
          <IncidentList incidents={data.incidents} />
          <AgentTimeline executions={latestIncident?.agent_executions ?? []} />
        </div>
        <div className="stack">
          <PendingApprovals approvals={data.approvals} />
          <EvaluationCharts evaluation={data.evaluation} />
        </div>
      </div>
    </>
  );
}
