import { getApprovals, getEvaluationSummary, getIncidents } from "@/services/apiClient";
import { DashboardSnapshot } from "@/store/dashboardStore";

export async function getDashboardData(): Promise<DashboardSnapshot> {
  const [incidents, approvals, evaluation] = await Promise.all([
    getIncidents(),
    getApprovals(),
    getEvaluationSummary()
  ]);

  return {
    incidents,
    approvals,
    evaluation
  };
}
