export type Incident = {
  id: string;
  title: string;
  severity: string;
  status: string;
  source: string;
  summary: string;
  incident_type?: string | null;
  classification_confidence?: number | null;
};

export type AgentExecution = {
  id: string;
  agent_name: string;
  status: string;
  created_at: string;
  output?: Record<string, unknown> | null;
};

export type IncidentDetail = Incident & {
  agent_executions?: AgentExecution[];
  graph_thread_id?: string | null;
};

export type ApprovalItem = {
  incident_id: string;
  status: string;
  summary: string;
  actions: string[];
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
};

export type EvaluationSummary = {
  count: number;
  results?: Array<Record<string, unknown>>;
  summary: {
    classification_accuracy: number;
    rootcause_accuracy: number;
    grounding_score: number;
    hallucination_score: number;
    blast_radius_score: number;
    safety_score: number;
    workflow_completion?: number;
  };
};

export type GraphNode = {
  id: string;
  status: string;
};

export type GraphEdge = {
  source: string;
  target: string;
};

export type GraphStateResponse = {
  thread_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  state: Record<string, unknown>;
};
