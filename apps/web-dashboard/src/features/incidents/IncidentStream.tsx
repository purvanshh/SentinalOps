"use client";

import { useEffect, useState } from "react";

import { streamIncident } from "@/services/apiClient";

type IncidentStreamProps = {
  incidentId: string;
};

export function IncidentStream({ incidentId }: IncidentStreamProps) {
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const socket = streamIncident(incidentId, (message) => {
      if (message && typeof message === "object") {
        setPayload(message as Record<string, unknown>);
      }
    });
    return () => {
      socket?.close();
    };
  }, [incidentId]);

  return (
    <section className="trace-card">
      <div className="eyebrow">Live Stream</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Incident stream
      </h3>
      <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
        {payload ? JSON.stringify(payload, null, 2) : "Waiting for stream updates..."}
      </pre>
    </section>
  );
}
