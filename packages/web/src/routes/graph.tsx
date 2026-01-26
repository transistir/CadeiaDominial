import { useMemo } from "react";
import { ReactFlow, Background, Controls } from "@xyflow/react";

const GraphRoute = () => {
  const { nodes, edges } = useMemo(
    () => ({
      nodes: [
        { id: "parcel", position: { x: 0, y: 80 }, data: { label: "Parcel 451" } },
        { id: "transfer", position: { x: 280, y: 0 }, data: { label: "Transfer 1998" } },
        { id: "registry", position: { x: 280, y: 160 }, data: { label: "Registry Entry" } }
      ],
      edges: [
        { id: "parcel-transfer", source: "parcel", target: "transfer" },
        { id: "parcel-registry", source: "parcel", target: "registry" }
      ]
    }),
    []
  );

  return (
    <section className="graph-page">
      <header>
        <p className="hero-eyebrow">Case Map</p>
        <h1>Title flow preview</h1>
        <p>Follow the chain from parcel to transfer and final registry note.</p>
      </header>
      <div className="graph-shell">
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background gap={24} size={1.5} color="#d5c9b8" />
          <Controls position="bottom-right" />
        </ReactFlow>
      </div>
    </section>
  );
};

export default GraphRoute;
