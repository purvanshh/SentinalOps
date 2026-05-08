import { EvaluationCharts } from "@/features/evaluations/EvaluationCharts";
import { getEvaluationSummary } from "@/services/apiClient";

export default async function EvaluationsPage() {
  const evaluation = await getEvaluationSummary();

  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr", marginTop: 24 }}>
      <EvaluationCharts evaluation={evaluation} />
    </div>
  );
}
