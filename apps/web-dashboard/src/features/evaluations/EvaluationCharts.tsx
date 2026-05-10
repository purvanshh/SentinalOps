import { asPercent } from "@/lib/format";
import { EvaluationSummary } from "@/types/dashboard";

type EvaluationChartsProps = {
  evaluation: EvaluationSummary;
};

const metricLabels: Record<string, string> = {
  classification_accuracy: "Classification",
  rootcause_accuracy: "Root Cause",
  grounding_score: "Grounding",
  hallucination_score: "Hallucination Guard",
  blast_radius_score: "Blast Radius",
  safety_score: "Safety",
  workflow_completion: "Workflow Completion"
};

export function EvaluationCharts({ evaluation }: EvaluationChartsProps) {
  return (
    <section className="list-card">
      <div className="eyebrow">Evaluation</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Release confidence snapshot
      </h3>
      {Object.entries(evaluation.summary).map(([key, value]) => (
        <div className="metric-row" key={key}>
          <div className="row-top">
            <strong>{metricLabels[key] ?? key}</strong>
            <span>{asPercent(value)}</span>
          </div>
          <div
            style={{
              height: 10,
              borderRadius: 999,
              background: "rgba(65,49,33,0.08)",
              overflow: "hidden"
            }}
          >
            <div
              style={{
                width: `${Math.max(4, value * 100)}%`,
                height: "100%",
                borderRadius: 999,
                background: "linear-gradient(90deg, var(--accent), var(--accent-soft))"
              }}
            />
          </div>
        </div>
      ))}
    </section>
  );
}
