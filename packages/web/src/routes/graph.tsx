import { useState } from "react";
import { GraphView } from "../graph";
import { generateMockGraph, type MockShape } from "../graph/mock";
import "./graph.css";

function GraphRoute() {
  const [shape, setShape] = useState<MockShape>("complex");

  const graph = generateMockGraph(shape);

  return (
    <div className="graph-page">
      <div className="graph-page__toolbar">
        <select
          data-testid="mock-shape-select"
          value={shape}
          onChange={(e) => setShape(e.target.value as MockShape)}
        >
          <option value="linear">Linear</option>
          <option value="branching">Branching</option>
          <option value="merge">Merge</option>
          <option value="complex">Complexo</option>
        </select>
      </div>
      <GraphView graph={graph} />
    </div>
  );
}

export default GraphRoute;
