import { IncidentList } from "@/features/incidents/IncidentList";
import { getIncidents } from "@/services/apiClient";

export default async function IncidentsPage() {
  const incidents = await getIncidents();

  return (
    <div className="grid" style={{ gridTemplateColumns: "1fr", marginTop: 24 }}>
      <IncidentList incidents={incidents} />
    </div>
  );
}
