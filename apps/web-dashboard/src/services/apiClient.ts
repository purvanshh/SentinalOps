import { ApprovalItem, EvaluationSummary, Incident } from "@/types/dashboard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function safeFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: 10 }
    });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function getIncidents(): Promise<Incident[]> {
  return safeFetch<Incident[]>("/incidents", [
    {
      id: "demo-incident-1",
      title: "Payment API latency exceeded threshold",
      severity: "high",
      status: "awaiting_approval",
      source: "prometheus",
      summary: "Latency crossed p99 threshold after the latest payment rollout.",
      incident_type: "deployment_regression",
      classification_confidence: 0.91
    },
    {
      id: "demo-incident-2",
      title: "Cache-backed checkout slowdown",
      severity: "medium",
      status: "resolved",
      source: "prometheus",
      summary: "Cache misses caused a rise in backend latency before auto-recovery.",
      incident_type: "cache_degradation",
      classification_confidence: 0.78
    }
  ]);
}

export async function getApprovals(): Promise<ApprovalItem[]> {
  return safeFetch<ApprovalItem[]>("/approvals", [
    {
      incident_id: "demo-incident-1",
      status: "awaiting_approval",
      summary: "Rollback deployment before user impact expands further.",
      actions: ["rollback deployment", "restart payment-api"],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
  ]);
}

export async function getEvaluationSummary(): Promise<EvaluationSummary> {
  return safeFetch<EvaluationSummary>("/evaluations/summary", {
    count: 2,
    summary: {
      classification_accuracy: 1,
      rootcause_accuracy: 1,
      grounding_score: 1,
      hallucination_score: 1,
      blast_radius_score: 1,
      safety_score: 1
    }
  });
}
