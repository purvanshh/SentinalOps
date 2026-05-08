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

export type ApprovalItem = {
  incident_id: string;
  status: string;
  summary: string;
  actions: string[];
  created_at: string;
  updated_at: string;
};

export type EvaluationSummary = {
  count: number;
  summary: {
    classification_accuracy: number;
    rootcause_accuracy: number;
    grounding_score: number;
    hallucination_score: number;
    blast_radius_score: number;
    safety_score: number;
  };
};
