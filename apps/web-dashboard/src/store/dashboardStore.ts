import { ApprovalItem, EvaluationSummary, Incident } from "@/types/dashboard";

export type DashboardSnapshot = {
  incidents: Incident[];
  approvals: ApprovalItem[];
  evaluation: EvaluationSummary;
};
