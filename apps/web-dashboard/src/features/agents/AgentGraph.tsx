import { GraphStateResponse } from "@/types/dashboard";

type AgentGraphProps = {
  graph: GraphStateResponse;
};

export function AgentGraph({ graph }: AgentGraphProps) {
  return (
    <section className="trace-card">
      <div className="eyebrow">Graph View</div>
      <h3 className="title" style={{ fontSize: "1.5rem", marginTop: 8 }}>
        Workflow graph
      </h3>
      <div className="trace-flow">
        {graph.nodes.map((node) => (
          <div className="trace-node" key={node.id}>
            <div className="row-top">
              <strong>{node.id.replaceAll("_", " ")}</strong>
              <span className={`pill ${node.status === "completed" ? "success" : node.status === "active" ? "warning" : ""}`}>
                {node.status}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="muted" style={{ marginTop: 12 }}>
        {graph.edges.map((edge) => `${edge.source} -> ${edge.target}`).join(" | ")}
      </div>
    </section>
  );
}
