import { GraphPreview } from "../graph/GraphPreview";
import basicGraph from "../graph/fixtures/basic-graph.json";
import type { GraphJson } from "../graph/types";

const GraphRoute = () => {
  return (
    <GraphPreview graph={basicGraph as GraphJson} />
  );
};

export default GraphRoute;
