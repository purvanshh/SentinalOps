import {
  ApprovalItem,
  EvaluationSummary,
  GraphEdge,
  GraphNode,
  GraphStateResponse,
  Incident,
  IncidentDetail
} from "@/types/dashboard";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const AUTH_TOKEN = process.env.NEXT_PUBLIC_DEMO_BEARER_TOKEN ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}),
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Request failed for ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function getIncidents(): Promise<Incident[]> {
  return request<Incident[]>("/incidents");
}

export async function getIncident(id: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/incidents/${id}`);
}

export async function getApprovals(): Promise<ApprovalItem[]> {
  return request<ApprovalItem[]>("/approvals");
}

export async function getEvaluationSummary(): Promise<EvaluationSummary> {
  return request<EvaluationSummary>("/evaluations/summary");
}

export async function getGraphState(id: string): Promise<GraphStateResponse> {
  return request<GraphStateResponse>(`/graph/incidents/${id}/graph-state`);
}

export async function decideApproval(incidentId: string, approved: boolean, note = ""): Promise<{ status: string }> {
  return request<{ status: string }>(`/approvals/${incidentId}`, {
    method: "POST",
    body: JSON.stringify({ approved, note })
  });
}

export function streamIncident(incidentId: string, onMessage: (payload: unknown) => void): WebSocket | null {
  if (typeof window === "undefined") {
    return null;
  }
  const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  const socket = new WebSocket(`${wsBase}/ws/incidents/${incidentId}/stream`);
  socket.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      onMessage(event.data);
    }
  };
  return socket;
}
