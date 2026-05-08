import Link from "next/link";

import { asPercent, titleCase } from "@/lib/format";
import { Incident } from "@/types/dashboard";

type IncidentListProps = {
  incidents: Incident[];
};

export function IncidentList({ incidents }: IncidentListProps) {
  return (
    <section className="list-card">
      <div className="page-header" style={{ marginBottom: 12 }}>
        <div>
          <div className="eyebrow">Incident Board</div>
          <h2>Active command surface</h2>
        </div>
        <span className="pill">{incidents.length} tracked incidents</span>
      </div>
      {incidents.map((incident) => (
        <div className="incident-row" key={incident.id}>
          <div className="row-top">
            <div>
              <h3 className="title">{incident.title}</h3>
              <p className="muted">{incident.summary}</p>
            </div>
            <span className={`pill ${incident.status.includes("resolved") ? "success" : incident.status.includes("approval") ? "warning" : ""}`}>
              {titleCase(incident.status)}
            </span>
          </div>
          <div className="row-top">
            <div className="muted">
              {titleCase(incident.severity)} severity
              {" · "}
              {titleCase(incident.incident_type ?? "unknown")}
              {" · "}
              confidence {asPercent(incident.classification_confidence)}
            </div>
            <div className="actions">
              <Link className="button secondary" href={`/incidents/${incident.id}`}>
                View trace
              </Link>
              <Link className="button primary" href="/approvals">
                Open approval center
              </Link>
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
